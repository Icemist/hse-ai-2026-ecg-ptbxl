"""Скачивает PTB-XL с PhysioNet и распаковывает в data/raw/ptb-xl.

Запуск из корня репозитория:
    python scripts/download_ptbxl.py             # архив ~1,7 ГБ, на диске ~3 ГБ
    python scripts/download_ptbxl.py --keep-zip  # не удалять архив после распаковки

Внутри: ptbxl_database.csv (разметка и метаданные), scp_statements.csv (словарь
диагнозов SCP-ECG), records100/ и records500/ (сигналы 100 и 500 Гц в формате WFDB).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.0.3"
SLUG = f"ptb-xl-a-large-publicly-available-electrocardiography-dataset-{VERSION}"
URL = f"https://physionet.org/static/published-projects/ptb-xl/{SLUG}.zip"

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TARGET = RAW / "ptb-xl"
ZIP = RAW / f"{SLUG}.zip"
REQUIRED = ["ptbxl_database.csv", "scp_statements.csv", "records100", "records500"]


def _progress(blocks: int, block_size: int, total: int) -> None:
    done = blocks * block_size
    if total > 0:
        pct = min(100, done * 100 // total)
        sys.stdout.write(f"\r  {done / 2**30:.2f} / {total / 2**30:.2f} ГБ  {pct:3d}%")
    else:
        sys.stdout.write(f"\r  {done / 2**30:.2f} ГБ")
    sys.stdout.flush()


def is_complete(path: Path) -> bool:
    return all((path / name).exists() for name in REQUIRED)


def download(keep_zip: bool) -> None:
    if is_complete(TARGET):
        print(f"PTB-XL уже на месте: {TARGET}")
        return

    RAW.mkdir(parents=True, exist_ok=True)
    if not ZIP.exists():
        print(f"Скачиваю {URL}")
        tmp = ZIP.with_suffix(".part")
        urllib.request.urlretrieve(URL, tmp, reporthook=_progress)
        tmp.rename(ZIP)
        print()
    else:
        print(f"Архив уже скачан: {ZIP}")

    print("Распаковываю...")
    with zipfile.ZipFile(ZIP) as zf:
        zf.extractall(RAW)
    extracted = RAW / SLUG
    if TARGET.exists():
        shutil.rmtree(TARGET)
    extracted.rename(TARGET)

    if not is_complete(TARGET):
        missing = [n for n in REQUIRED if not (TARGET / n).exists()]
        sys.exit(f"После распаковки не хватает: {missing}")

    if not keep_zip:
        ZIP.unlink()
    print(f"Готово: {TARGET}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep-zip", action="store_true", help="не удалять архив после распаковки")
    args = parser.parse_args()
    download(keep_zip=args.keep_zip)


if __name__ == "__main__":
    main()
