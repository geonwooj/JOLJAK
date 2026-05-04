import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import softmax

def pairwise_in_out_stats(vectors, labels, domain_order, target_domain=None):
    vectors = l2_normalize_rows(vectors)
    labels = np.asarray(labels, dtype=str)

    groups = {}
    for d in domain_order:
        idx = np.where(labels == d)[0]
        groups[d] = vectors[idx]

    intra_vals = []
    inter_vals = []

    if target_domain is None:
        for i, d1 in enumerate(domain_order):
            X = groups[d1]

            if len(X) > 1:
                sim = X @ X.T
                mask = ~np.eye(len(X), dtype=bool)
                intra_vals.extend(sim[mask].tolist())

            for d2 in domain_order[i + 1:]:
                Y = groups[d2]
                if len(X) > 0 and len(Y) > 0:
                    sim = X @ Y.T
                    inter_vals.extend(sim.reshape(-1).tolist())

    else:
        target_domain = str(target_domain)
        X = groups[target_domain]

        if len(X) > 1:
            sim = X @ X.T
            mask = ~np.eye(len(X), dtype=bool)
            intra_vals.extend(sim[mask].tolist())

        for d in domain_order:
            if d == target_domain:
                continue

            Y = groups[d]
            if len(X) > 0 and len(Y) > 0:
                sim = X @ Y.T
                inter_vals.extend(sim.reshape(-1).tolist())

    mu_in = float(np.mean(intra_vals)) if len(intra_vals) > 0 else 0.0
    mu_out = float(np.mean(inter_vals)) if len(inter_vals) > 0 else 0.0

    sigma_in = float(np.std(intra_vals)) if len(intra_vals) > 0 else 0.0
    sigma_out = float(np.std(inter_vals)) if len(inter_vals) > 0 else 0.0

    return {
        "mu_in": mu_in,
        "mu_out": mu_out,
        "sigma_in": sigma_in,
        "sigma_out": sigma_out,
        "count_in": len(intra_vals),
        "count_out": len(inter_vals),
    }


def calculate_dynamic_weights_from_stats(stats_dict, eps_j=0.05, tau=1.5):
    results = {}
    s_values = []

    for section, data in stats_dict.items():
        mu_in = float(data["mu_in"])
        mu_out = float(data["mu_out"])
        sigma_in = float(data["sigma_in"])
        sigma_out = float(data["sigma_out"])

        j = mu_in - mu_out
        sigma_total = float(np.sqrt(sigma_in ** 2 + sigma_out ** 2))
        j_prime = max(j - eps_j, 0.0)
        s = j_prime / (sigma_total + 1e-6)

        results[section] = {
            "mu_in": mu_in,
            "mu_out": mu_out,
            "J": j,
            "sigma_in": sigma_in,
            "sigma_out": sigma_out,
            "sigma": sigma_total,
            "S": s,
            "count_in": int(data.get("count_in", 0)),
            "count_out": int(data.get("count_out", 0)),
        }

        s_values.append(s)

    weights = softmax(np.asarray(s_values, dtype=np.float32) / tau)

    for i, section in enumerate(stats_dict.keys()):
        results[section]["W"] = float(weights[i])

    return results


def select_best_mode_by_section(centered_results, section_order, mode_order, force_modes=None):
    if force_modes is not None:
        return dict(force_modes)

    best = {}

    for section in section_order:
        best_mode = None
        best_sep = -1e18

        for mode in mode_order:
            sep = centered_results[section][mode]["metrics"]["separation"]

            if sep > best_sep:
                best_sep = sep
                best_mode = mode

        best[section] = best_mode

    return best


def make_vector_map(pack):
    vectors = pack["vectors"]
    labels = pack["labels"]
    doc_ids = pack["doc_ids"]

    out = {}

    for i in range(len(labels)):
        key = (str(labels[i]), str(doc_ids[i]))
        out[key] = vectors[i]

    return out


def align_selected_sections(centered_results, best_modes, section_order, domain_order):
    section_maps = {}

    for section in section_order:
        mode = best_modes[section]
        pack = centered_results[section][mode]
        section_maps[section] = make_vector_map(pack)

    common_keys = None

    for section in section_order:
        keys = set(section_maps[section].keys())
        common_keys = keys if common_keys is None else common_keys & keys

    common_keys = sorted(
        list(common_keys),
        key=lambda x: (
            domain_order.index(x[0]) if x[0] in domain_order else 999,
            x[1],
        ),
    )

    labels = [k[0] for k in common_keys]
    doc_ids = [k[1] for k in common_keys]

    vectors_by_section = {}

    for section in section_order:
        vectors_by_section[section] = np.vstack(
            [section_maps[section][k] for k in common_keys]
        ).astype(np.float32)

    return {
        "keys": common_keys,
        "labels": labels,
        "doc_ids": doc_ids,
        "vectors_by_section": vectors_by_section,
    }


def build_stats_dict_from_aligned(aligned_pack, section_order, domain_order, target_domain=None):
    labels = aligned_pack["labels"]
    vectors_by_section = aligned_pack["vectors_by_section"]

    stats_dict = {}

    for section in section_order:
        stats = pairwise_in_out_stats(
            vectors=vectors_by_section[section],
            labels=labels,
            domain_order=domain_order,
            target_domain=target_domain,
        )
        stats_dict[section] = stats

    return stats_dict


def calculate_global_and_domain_dynamic_weights(
    aligned_pack,
    section_order,
    domain_order,
    eps_j=0.05,
    tau=1.5,
):
    global_stats = build_stats_dict_from_aligned(
        aligned_pack=aligned_pack,
        section_order=section_order,
        domain_order=domain_order,
        target_domain=None,
    )

    global_result = calculate_dynamic_weights_from_stats(
        global_stats,
        eps_j=eps_j,
        tau=tau,
    )

    domain_results = {}

    for domain in domain_order:
        domain_stats = build_stats_dict_from_aligned(
            aligned_pack=aligned_pack,
            section_order=section_order,
            domain_order=domain_order,
            target_domain=domain,
        )

        domain_results[domain] = calculate_dynamic_weights_from_stats(
            domain_stats,
            eps_j=eps_j,
            tau=tau,
        )

    return global_result, domain_results


def extract_weight_map(weight_result, section_order):
    return {
        section: float(weight_result[section]["W"])
        for section in section_order
    }


def fuse_just_sum3(aligned_pack, section_order):
    vectors_by_section = aligned_pack["vectors_by_section"]

    out = np.zeros_like(vectors_by_section[section_order[0]], dtype=np.float32)

    for section in section_order:
        out += vectors_by_section[section]

    out = out / float(len(section_order))
    return l2_normalize_rows(out)


def fuse_dynamic_global(aligned_pack, global_weight_result, section_order):
    vectors_by_section = aligned_pack["vectors_by_section"]
    weights = extract_weight_map(global_weight_result, section_order)

    out = np.zeros_like(vectors_by_section[section_order[0]], dtype=np.float32)

    for section in section_order:
        out += float(weights[section]) * vectors_by_section[section]

    return l2_normalize_rows(out)


def fuse_dynamic_by_domain(aligned_pack, domain_weight_results, section_order, domain_order):
    labels = np.asarray(aligned_pack["labels"], dtype=str)
    vectors_by_section = aligned_pack["vectors_by_section"]

    out = np.zeros_like(vectors_by_section[section_order[0]], dtype=np.float32)

    for domain in domain_order:
        idx = np.where(labels == domain)[0]
        if len(idx) == 0:
            continue

        weights = extract_weight_map(domain_weight_results[domain], section_order)

        for section in section_order:
            out[idx] += float(weights[section]) * vectors_by_section[section][idx]

    return l2_normalize_rows(out)


def dynamic_result_to_df(global_result, domain_results, best_modes, section_order, domain_order):
    rows = []

    for section in section_order:
        r = global_result[section]

        rows.append({
            "weight_scope": "global",
            "domain": "ALL",
            "section": section,
            "best_mode": best_modes[section],
            "mu_in": r["mu_in"],
            "mu_out": r["mu_out"],
            "J": r["J"],
            "sigma_in": r["sigma_in"],
            "sigma_out": r["sigma_out"],
            "sigma": r["sigma"],
            "S": r["S"],
            "W": r["W"],
            "count_in": r["count_in"],
            "count_out": r["count_out"],
        })

    for domain in domain_order:
        result = domain_results[domain]

        for section in section_order:
            r = result[section]

            rows.append({
                "weight_scope": "domain",
                "domain": domain,
                "section": section,
                "best_mode": best_modes[section],
                "mu_in": r["mu_in"],
                "mu_out": r["mu_out"],
                "J": r["J"],
                "sigma_in": r["sigma_in"],
                "sigma_out": r["sigma_out"],
                "sigma": r["sigma"],
                "S": r["S"],
                "W": r["W"],
                "count_in": r["count_in"],
                "count_out": r["count_out"],
            })

    return pd.DataFrame(rows)