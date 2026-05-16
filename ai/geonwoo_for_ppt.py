from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
from scipy.special import softmax

STATS_DIR = Path("outputs/section_stats")
CACHE_ROOT = Path("data/section_embedding_cache")
OUTPUT_DIR = Path("outputs/section_weights")

SECTIONS = ("abstract", "claims", "description")
EPS = 1e-8


def l2_normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    if n < EPS:
        return np.zeros_like(v, dtype=np.float32)
    return (v / n).astype(np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = l2_normalize(a)
    b = l2_normalize(b)
    if float(np.linalg.norm(a)) < EPS or float(np.linalg.norm(b)) < EPS:
        return 0.0
    return float(np.dot(a, b))


def load_field_stats(stats_dir: Path, fields: List[str]) -> Dict[str, Dict[str, np.ndarray]]:
    loaded = {}
    for field in fields:
        path = stats_dir / f"{field}_stats.npz"
        if not path.exists():
            raise FileNotFoundError(f"stats 파일이 없습니다: {path}")
        data = np.load(path, allow_pickle=True)
        loaded[field] = {
            "mean_abstract": data["mean_abstract"].astype(np.float32),
            "mean_claims": data["mean_claims"].astype(np.float32),
            "mean_description": data["mean_description"].astype(np.float32),
            "std_abstract": data["std_abstract"].astype(np.float32),
            "std_claims": data["std_claims"].astype(np.float32),
            "std_description": data["std_description"].astype(np.float32),
            "n_docs": data["n_docs"],
        }
    return loaded


def list_cached_vectors(cache_root: Path, field: str, section: str) -> List[Path]:
    section_dir = cache_root / field / section
    if not section_dir.exists():
        raise FileNotFoundError(f"cache 디렉토리가 없습니다: {section_dir}")
    return sorted(section_dir.glob("*.npy"))


def compute_weights(
    stats: Dict[str, Dict[str, np.ndarray]],
    cache_root: Path,
    fields: List[str],
    eps_j: float,
    tau: float,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    results: Dict[str, Dict[str, Dict[str, float]]] = {}

    for target_field in fields:
        section_scores: Dict[str, Dict[str, float]] = {}
        s_values: List[float] = []

        for section in SECTIONS:
            proto = stats[target_field][f"mean_{section}"]
            in_scores = []
            out_scores = []

            for source_field in fields:
                vec_paths = list_cached_vectors(cache_root, source_field, section)
                for vec_path in vec_paths:
                    vec = np.load(vec_path)
                    score = cosine(vec, proto)
                    if source_field == target_field:
                        in_scores.append(score)
                    else:
                        out_scores.append(score)

            in_arr = np.asarray(in_scores, dtype=np.float32)
            out_arr = np.asarray(out_scores, dtype=np.float32)

            mu_in = float(np.mean(in_arr)) if len(in_arr) else 0.0
            mu_out = float(np.mean(out_arr)) if len(out_arr) else 0.0
            sigma_in = float(np.std(in_arr)) if len(in_arr) else 0.0
            sigma_out = float(np.std(out_arr)) if len(out_arr) else 0.0

            j = mu_in - mu_out
            sigma_total = float(np.sqrt(sigma_in ** 2 + sigma_out ** 2))
            j_prime = max(j - eps_j, 0.0)
            s = j_prime / (sigma_total + 1e-6)

            section_scores[section] = {
                "mu_in": mu_in,
                "mu_out": mu_out,
                "sigma_in": sigma_in,
                "sigma_out": sigma_out,
                "J": j,
                "sigma": sigma_total,
                "S": s,
                "threshold_eps_j": float(eps_j),
                "softmax_tau": float(tau),
            }
            s_values.append(s)

        weights = softmax(np.asarray(s_values, dtype=np.float32) / max(tau, 1e-6))
        for idx, section in enumerate(SECTIONS):
            section_scores[section]["W"] = float(weights[idx])

        results[target_field] = section_scores

    return results


def save_weight_npz_per_field(output_dir: Path, field_results: Dict[str, Dict[str, Dict[str, float]]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for field, section_info in field_results.items():
        payload = {
            "field_name": np.asarray([field], dtype="U64"),
            "sections": np.asarray(SECTIONS, dtype="U32"),
        }
        for section in SECTIONS:
            payload[f"w_{section}"] = np.asarray([section_info[section]["W"]], dtype=np.float32)
            payload[f"{section}_mu_in"] = np.asarray([section_info[section]["mu_in"]], dtype=np.float32)
            payload[f"{section}_mu_out"] = np.asarray([section_info[section]["mu_out"]], dtype=np.float32)
            payload[f"{section}_sigma_in"] = np.asarray([section_info[section]["sigma_in"]], dtype=np.float32)
            payload[f"{section}_sigma_out"] = np.asarray([section_info[section]["sigma_out"]], dtype=np.float32)
            payload[f"{section}_J"] = np.asarray([section_info[section]["J"]], dtype=np.float32)
            payload[f"{section}_sigma"] = np.asarray([section_info[section]["sigma"]], dtype=np.float32)
            payload[f"{section}_S"] = np.asarray([section_info[section]["S"]], dtype=np.float32)

        out_path = output_dir / f"{field}_weights.npz"
        np.savez_compressed(out_path, **payload)
        print(f"[SAVED] {out_path}")


def save_weight_csv(output_dir: Path, field_results: Dict[str, Dict[str, Dict[str, float]]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "field_section_weights.csv"

    rows = []
    for field, sec_dict in field_results.items():
        for section in SECTIONS:
            rows.append({
                "field": field,
                "section": section,
                **sec_dict[section],
            })

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field", "section",
                "mu_in", "mu_out",
                "sigma_in", "sigma_out",
                "J", "sigma", "S", "W",
                "threshold_eps_j", "softmax_tau",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[SAVED] {csv_path}")


def save_weight_json(output_dir: Path, field_results: Dict[str, Dict[str, Dict[str, float]]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "field_section_weights.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(field_results, f, ensure_ascii=False, indent=2)
    print(f"[SAVED] {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "1단계에서 저장한 *_stats.npz 와 section embedding cache를 이용해 "
            "Fisher/SNR 기반의 분야별 section weight를 계산하고 *_weights.npz 로 저장합니다."
        )
    )
    parser.add_argument("--stats_dir", type=Path, default=STATS_DIR)
    parser.add_argument("--cache_root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--output_dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--fields", nargs="+", required=True)
    parser.add_argument("--eps_j", type=float, default=0.05)
    parser.add_argument("--tau", type=float, default=1.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = load_field_stats(args.stats_dir, args.fields)
    field_results = compute_weights(
        stats=stats,
        cache_root=args.cache_root,
        fields=args.fields,
        eps_j=args.eps_j,
        tau=args.tau,
    )
    save_weight_npz_per_field(args.output_dir, field_results)
    save_weight_csv(args.output_dir, field_results)
    save_weight_json(args.output_dir, field_results)

    print("\n[SUMMARY]")
    for field in args.fields:
        print(f"\n[{field}]")
        for section in SECTIONS:
            info = field_results[field][section]
            print(
                f"  {section:12s} | W={info['W']:.4f} | "
                f"mu_in={info['mu_in']:.4f} | mu_out={info['mu_out']:.4f} | "
                f"J={info['J']:.4f} | S={info['S']:.4f}"
            )


if __name__ == "__main__":
    main()
