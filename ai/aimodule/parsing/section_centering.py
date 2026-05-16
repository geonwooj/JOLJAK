import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

def l2_normalize_rows(X: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    X = np.asarray(X, dtype=np.float32)

    if X.ndim == 1:
        X = X.reshape(1, -1)

    norms = np.linalg.norm(X, axis=1, keepdims=True)
    return (X / np.maximum(norms, eps)).astype(np.float32)


def apply_centering(vectors: np.ndarray, center: np.ndarray, alpha: float = 1.0, renorm: bool = True, eps: float = 1e-8) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)

    if vectors.size == 0:
        return vectors.astype(np.float32)

    center = np.asarray(center, dtype=np.float32).reshape(1, -1)
    centered = vectors - float(alpha) * center

    if renorm:
        centered = l2_normalize_rows(centered, eps=eps)

    return centered.astype(np.float32)


def compute_section_centers(raw_results, section_order, source_mode="x"):
    section_centers = {}
    section_center_norms = {}

    for section in section_order:
        vecs = raw_results[section][source_mode]["raw_vectors"]

        if len(vecs) > 0:
            center = np.mean(vecs, axis=0, keepdims=True).astype(np.float32)
            section_centers[section] = center
            section_center_norms[section] = float(np.linalg.norm(center))
        else:
            section_centers[section] = None
            section_center_norms[section] = 0.0

    return section_centers, section_center_norms


def compute_global_x_center(raw_results, section_order, source_mode="x"):
    bank = []

    for section in section_order:
        vecs = raw_results[section][source_mode]["raw_vectors"]
        if len(vecs) > 0:
            bank.append(vecs)

    if len(bank) == 0:
        return None, 0.0

    X = np.concatenate(bank, axis=0).astype(np.float32)
    center = np.mean(X, axis=0, keepdims=True).astype(np.float32)
    norm = float(np.linalg.norm(center))

    return center, norm


def build_domain_mean_matrix(vectors, labels, domain_order):
    vectors = l2_normalize_rows(vectors)
    labels = np.asarray(labels, dtype=str)

    matrix = np.zeros((len(domain_order), len(domain_order)), dtype=np.float64)

    groups = {}
    for d in domain_order:
        idx = np.where(labels == d)[0]
        groups[d] = vectors[idx]

    for i, d1 in enumerate(domain_order):
        X = groups[d1]

        for j, d2 in enumerate(domain_order):
            Y = groups[d2]

            if len(X) == 0 or len(Y) == 0:
                matrix[i, j] = 0.0
                continue

            sim = X @ Y.T

            if d1 == d2:
                n = sim.shape[0]
                if n <= 1:
                    matrix[i, j] = 0.0
                else:
                    mask = ~np.eye(n, dtype=bool)
                    matrix[i, j] = float(sim[mask].mean())
            else:
                matrix[i, j] = float(sim.mean())

    return matrix


def evaluate_vectors(vectors, labels, domain_order):
    vectors = np.asarray(vectors, dtype=np.float32)

    if len(labels) == 0 or vectors.size == 0:
        return {
            "intra_mean": 0.0,
            "inter_mean": 0.0,
            "separation": 0.0,
            "domain_mean_matrix": np.zeros((len(domain_order), len(domain_order)), dtype=np.float64),
        }

    vectors = l2_normalize_rows(vectors)
    labels = np.asarray(labels, dtype=str)

    groups = {}
    for d in domain_order:
        idx = np.where(labels == d)[0]
        groups[d] = vectors[idx]

    intra_vals = []
    inter_vals = []

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

    intra_mean = float(np.mean(intra_vals)) if len(intra_vals) > 0 else 0.0
    inter_mean = float(np.mean(inter_vals)) if len(inter_vals) > 0 else 0.0

    return {
        "intra_mean": intra_mean,
        "inter_mean": inter_mean,
        "separation": intra_mean - inter_mean,
        "domain_mean_matrix": build_domain_mean_matrix(vectors, labels, domain_order),
    }


def apply_fixed_centering(
    raw_results,
    section_order,
    mode_order,
    domain_order,
    center_scope="section",
    center_source_mode="x",
    section_centering_alpha=None,
    renorm=True,
    eps=1e-8,
):
    assert center_scope in ["section", "global_x"]

    if section_centering_alpha is None:
        section_centering_alpha = {section: 1.0 for section in section_order}

    centered_results = {section: {} for section in section_order}
    summary_rows = []

    if center_scope == "section":
        section_centers, center_norms = compute_section_centers(
            raw_results,
            section_order=section_order,
            source_mode=center_source_mode,
        )
    else:
        global_center, global_norm = compute_global_x_center(
            raw_results,
            section_order=section_order,
            source_mode=center_source_mode,
        )
        section_centers = {section: global_center for section in section_order}
        center_norms = {section: global_norm for section in section_order}

    for section in section_order:
        center = section_centers[section]

        for mode in mode_order:
            raw_pack = raw_results[section][mode]
            raw_vecs = raw_pack["raw_vectors"]
            labels = raw_pack["labels"]
            doc_ids = raw_pack["doc_ids"]

            if center is None or len(raw_vecs) == 0:
                centered_vecs = raw_vecs
            else:
                centered_vecs = apply_centering(
                    vectors=raw_vecs,
                    center=center,
                    alpha=section_centering_alpha.get(section, 1.0),
                    renorm=renorm,
                    eps=eps,
                )

            metrics = evaluate_vectors(centered_vecs, labels, domain_order)

            centered_results[section][mode] = {
                "vectors": centered_vecs,
                "labels": labels,
                "doc_ids": doc_ids,
                "metrics": metrics,
                "raw_metrics": raw_pack.get("raw_metrics", None),
                "center_scope": center_scope,
                "center_source_mode": center_source_mode,
                "center_norm": center_norms.get(section, 0.0),
            }

            summary_rows.append({
                "section": section,
                "mode": mode,
                "docs": len(labels),
                "center_scope": center_scope,
                "center_source_mode": center_source_mode,
                "center_norm": center_norms.get(section, 0.0),
                "intra_mean": metrics["intra_mean"],
                "inter_mean": metrics["inter_mean"],
                "separation": metrics["separation"],
            })

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values("separation", ascending=False).reset_index(drop=True)

    return centered_results, summary_df