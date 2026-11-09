from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecg_ptbxl.augmentation_data import BASE_URL, DEFAULT_DATA_DIR, download_subset  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--per-class", type=int, default=25)
    parser.add_argument("--multilabel-count", type=int, default=50)
    parser.add_argument("--seed", type=int, default=146)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--base-url", default=BASE_URL, help="HTTPS root of the versioned dataset")
    args = parser.parse_args()
    manifest = download_subset(
        args.data_dir,
        per_class=args.per_class,
        multilabel_count=args.multilabel_count,
        seed=args.seed,
        workers=args.workers,
        base_url=args.base_url,
    )
    print(f"Downloaded {len(manifest)} recordings from {manifest.patient_id.nunique()} patients")
    print(manifest["sampling_group"].value_counts().sort_index().to_string())
    print(f"Data directory: {args.data_dir.resolve()}")


if __name__ == "__main__":
    main()
