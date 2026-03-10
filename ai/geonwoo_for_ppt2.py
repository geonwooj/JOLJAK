from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import numpy as np

CACHE_ROOT = Path("data/section_embedding_cache")
WEIGHTS_DIR = Path("outputs/section_weights")
OUTPUT_DIR = Path("outputs/patent_vectors")

SECTIONS = ("abstract", "claims", "description")
EPS = 1e-8


def l2_normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    if n < EPS:
        return np.zeros_like(v, dtype=np.float32)
    return (v / n).astype(np.float32)


def load_weights(weights_dir: Path, field: str) -> Dict[str, float]:
    path = weights_dir / f"{field}_weights.npz"
    if not path.exists():
        raise FileNotFoundError(f"weights 파일이 없습니다: {path}")

    data = np.load(path, allow_pickle=True)
    return {
        "abstract": float(data["w_abstract"][0]),
        "claims": float(data["w_claims"][0]),
        "description": float(data["w_description"][0]),
    }


def list_patent_ids(cache_root: Path, field: str) -> List[str]:
    section_dir = cache_root / field / "abstract"
    if not section_dir.exists():
        raise FileNotFoundError(f"cache 디렉토리가 없습니다: {section_dir}")
    return sorted([p.stem for p in section_dir.glob("*.npy")])


def load_section_vec(cache_root: Path, field: str, patent_id: str, section: str) -> np.ndarray:
    path = cache_root / field / section / f"{patent_id}.npy"
    if not path.exists():
        raise FileNotFoundError(f"section vector가 없습니다: {path}")
    return np.load(path).astype(np.float32)


def fuse_patent_vector(
    abs_vec: np.ndarray,
    claims_vec: np.ndarray,
    desc_vec: np.ndarray,
    weights: Dict[str, float],
) -> np.ndarray:
    vec = (
        weights["abstract"] * abs_vec
        + weights["claims"] * claims_vec
        + weights["description"] * desc_vec
    )
    return l2_normalize(vec)


def save_field_patent_vectors(
    output_dir: Path,
    field: str,
    patent_vectors: Dict[str, np.ndarray],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{field}_patent_vectors.npz"
    np.savez_compressed(out_path, **{k: v.astype(np.float32) for k, v in patent_vectors.items()})
    print(f"[SAVED] {out_path}")
    return out_path


def save_all_patent_vectors(
    output_dir: Path,
    all_vectors: Dict[str, np.ndarray],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "all_patent_vectors.npz"
    np.savez_compressed(out_path, **{k: v.astype(np.float32) for k, v in all_vectors.items()})
    print(f"[SAVED] {out_path}")
    return out_path


def save_meta_csv(
    output_dir: Path,
    rows: List[Dict[str, str]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "patent_vector_meta.csv"

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "patent_id",
                "field",
                "npz_key",
                "vector_npz_path",
                "weight_npz_path",
                "w_abstract",
                "w_claims",
                "w_description",
                "abstract_vec_path",
                "claims_vec_path",
                "description_vec_path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[SAVED] {out_path}")
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "2단계에서 생성한 *_weights.npz 와 1단계의 section embedding cache를 이용해, "
            "각 특허의 최종 fused vector를 생성하고 npz로 저장합니다."
        )
    )
    parser.add_argument("--cache_root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--weights_dir", type=Path, default=WEIGHTS_DIR)
    parser.add_argument("--output_dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--fields", nargs="+", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_vectors: Dict[str, np.ndarray] = {}
    meta_rows: List[Dict[str, str]] = []

    for field in args.fields:
        weights = load_weights(args.weights_dir, field)
        patent_ids = list_patent_ids(args.cache_root, field)
        field_vectors: Dict[str, np.ndarray] = {}

        print(f"[INFO] field={field} / patents={len(patent_ids)}")
        for patent_id in patent_ids:
            abs_vec = load_section_vec(args.cache_root, field, patent_id, "abstract")
            claims_vec = load_section_vec(args.cache_root, field, patent_id, "claims")
            desc_vec = load_section_vec(args.cache_root, field, patent_id, "description")

            fused = fuse_patent_vector(abs_vec, claims_vec, desc_vec, weights)

            field_vectors[patent_id] = fused
            all_key = f"{field}__{patent_id}"
            all_vectors[all_key] = fused

            meta_rows.append({
                "patent_id": patent_id,
                "field": field,
                "npz_key": all_key,
                "vector_npz_path": str(args.output_dir / "all_patent_vectors.npz"),
                "weight_npz_path": str(args.weights_dir / f"{field}_weights.npz"),
                "w_abstract": f"{weights['abstract']:.8f}",
                "w_claims": f"{weights['claims']:.8f}",
                "w_description": f"{weights['description']:.8f}",
                "abstract_vec_path": str(args.cache_root / field / "abstract" / f"{patent_id}.npy"),
                "claims_vec_path": str(args.cache_root / field / "claims" / f"{patent_id}.npy"),
                "description_vec_path": str(args.cache_root / field / "description" / f"{patent_id}.npy"),
            })

        save_field_patent_vectors(args.output_dir, field, field_vectors)

    save_all_patent_vectors(args.output_dir, all_vectors)
    save_meta_csv(args.output_dir, meta_rows)

    print("\n[DONE]")
    print(f"- {args.output_dir / 'all_patent_vectors.npz'}")
    print(f"- {args.output_dir / 'patent_vector_meta.csv'}")
    for field in args.fields:
        print(f"- {args.output_dir / f'{field}_patent_vectors.npz'}")


if __name__ == "__main__":
    main()
