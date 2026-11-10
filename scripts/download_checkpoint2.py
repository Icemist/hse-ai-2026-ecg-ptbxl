"""Prepare the 100 Hz PTB-XL data used by the combined EDA notebook."""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecg_ptbxl.augmentation_data import (  # noqa: E402
    BASE_URL,
    METADATA_FILES,
    _download_file,
    download_subset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw/ptb-xl")
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    directory = args.data_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name in METADATA_FILES:
        _download_file(name, directory, base_url=args.base_url)
    metadata = pd.read_csv(directory / "ptbxl_database.csv")
    files = [
        f"{name}.{extension}" for name in metadata["filename_lr"] for extension in ("hea", "dat")
    ]
    missing = [
        name
        for name in files
        if not (directory / name).is_file() or (directory / name).stat().st_size == 0
    ]
    print(f"100 Hz recordings: {len(metadata)}; missing files: {len(missing)}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(_download_file, name, directory, base_url=args.base_url) for name in missing
        ]
        for completed, future in enumerate(as_completed(futures), 1):
            future.result()
            if completed % 1000 == 0 or completed == len(missing):
                print(f"Downloaded {completed}/{len(missing)} files", flush=True)
    # The original augmentation notebook retains its separate 175-patient sample.
    manifest = download_subset(workers=args.workers, base_url=args.base_url)
    print(f"Ready: {len(metadata)} recordings; augmentation sample: {len(manifest)}", flush=True)


if __name__ == "__main__":
    main()
