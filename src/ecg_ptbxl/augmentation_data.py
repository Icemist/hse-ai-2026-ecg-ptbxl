from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

import pandas as pd

VERSION = "1.0.3"
DATASET_URL = f"https://physionet.org/content/ptb-xl/{VERSION}/"
# PhysioNet mirror: https://registry.opendata.aws/ptb-xl/
BASE_URL = f"https://physionet-open.s3.amazonaws.com/ptb-xl/{VERSION}/"
CLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data" / "augmentation_ptbxl_1.0.3"
METADATA_FILES = ("ptbxl_database.csv", "scp_statements.csv")


def select_manifest(
    labelled: pd.DataFrame,
    *,
    per_class: int = 25,
    multilabel_count: int = 50,
    seed: int = 146,
) -> pd.DataFrame:
    """Select single-class strata plus a multi-label stratum from folds 1-8.

    Select at most one ECG per patient. Sorting by ecg_id makes selection
    independent of input row order. Raise an error if a group is too small.
    """
    if per_class < 1 or multilabel_count < 0:
        raise ValueError("per_class must be positive and multilabel_count non-negative")
    required = ["ecg_id", "patient_id", "strat_fold", "filename_lr", *CLASSES]
    missing = sorted(set(required) - set(labelled.columns))
    if missing:
        raise ValueError(f"Missing manifest columns: {missing}")
    if labelled["ecg_id"].duplicated().any():
        raise ValueError("ecg_id must be unique before sampling")
    if labelled[required].isna().any().any():
        raise ValueError("Identifiers, paths, folds and labels must not be missing")
    if not labelled[CLASSES].isin([0, 1]).all().all():
        raise ValueError("Target columns must be binary")

    pool = labelled.loc[labelled["strat_fold"].isin(range(1, 9))].copy()
    pool["n_labels"] = pool[CLASSES].sum(axis=1).astype(int)
    pool["has_target_label"] = pool["n_labels"] > 0
    groups = [
        (f"single_{name}", (pool["n_labels"] == 1) & (pool[name] == 1), per_class)
        for name in CLASSES
    ]
    groups.append(("multilabel", pool["n_labels"] > 1, multilabel_count))
    used_patients: set[object] = set()
    selected = []
    for index, (name, condition, count) in enumerate(groups):
        if count == 0:
            continue
        candidates = pool.loc[condition & ~pool["patient_id"].isin(used_patients)]
        candidates = candidates.sort_values("ecg_id").sample(frac=1, random_state=seed + index)
        candidates = candidates.drop_duplicates("patient_id")
        if len(candidates) < count:
            raise ValueError(
                f"Stratum {name}: need {count} distinct patients, have {len(candidates)}"
            )
        chosen = candidates.head(count).copy()
        chosen["sampling_group"] = name
        used_patients.update(chosen["patient_id"].tolist())
        selected.append(chosen)

    columns = [*required, "n_labels", "has_target_label", "sampling_group"]
    return pd.concat(selected, ignore_index=True)[columns]


def prepare_augmentation_labels(
    database_path: Path | str,
    statements_path: Path | str,
    *,
    labels_module_path: Path | str | None = None,
) -> pd.DataFrame:
    """Use notebooks/labels.py and attach WFDB paths by ecg_id."""
    module_path = Path(labels_module_path or ROOT / "notebooks" / "labels.py")
    spec = importlib.util.spec_from_file_location("augmentation_team_labels", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load label preparation from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if list(module.CLASSES) != CLASSES:
        raise ValueError("Label helper class order differs from CLASSES")
    labels = module.prepare_labels(database_path, statements_path)
    paths = pd.read_csv(database_path, usecols=["ecg_id", "filename_lr"])
    return labels.merge(paths, on="ecg_id", how="left", validate="one_to_one")


def build_manifest(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    per_class: int = 25,
    multilabel_count: int = 50,
    seed: int = 146,
    labels_module_path: Path | str | None = None,
) -> pd.DataFrame:
    """Prepare labels with the EDA helper, then select the study sample."""
    directory = Path(data_dir)
    labelled = prepare_augmentation_labels(
        directory / METADATA_FILES[0],
        directory / METADATA_FILES[1],
        labels_module_path=labels_module_path,
    )
    return select_manifest(
        labelled, per_class=per_class, multilabel_count=multilabel_count, seed=seed
    )


def _download_file(
    relative: str, directory: Path, *, attempts: int = 3, base_url: str = BASE_URL
) -> None:
    if not base_url.startswith("https://"):
        raise ValueError("Dataset downloads require an HTTPS base URL")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe dataset path: {relative}")
    target = directory.joinpath(*path.parts)
    if target.is_file() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                base_url.rstrip("/") + "/" + path.as_posix(),
                headers={"User-Agent": "PTBXL-augmentation-EDA/1.0"},
            )
            with urllib.request.urlopen(request, timeout=20) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out)
                expected = response.headers.get("Content-Length")
            if partial.stat().st_size == 0:
                raise OSError(f"Empty download: {relative}")
            if expected is not None and partial.stat().st_size != int(expected):
                raise OSError(f"Incomplete download: {relative}")
            partial.replace(target)
            return
        except (OSError, ValueError):
            partial.unlink(missing_ok=True)
            if attempt + 1 == attempts:
                raise
            time.sleep(attempt + 1)


def download_subset(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    per_class: int = 25,
    multilabel_count: int = 50,
    seed: int = 146,
    workers: int = 4,
    base_url: str = BASE_URL,
) -> pd.DataFrame:
    """Download metadata and selected WFDB headers/signals, then save a manifest."""
    if workers < 1:
        raise ValueError("workers must be positive")
    directory = Path(data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name in METADATA_FILES:
        _download_file(name, directory, base_url=base_url)
    manifest = build_manifest(
        directory, per_class=per_class, multilabel_count=multilabel_count, seed=seed
    )
    filenames = [
        f"{record}.{extension}"
        for record in manifest["filename_lr"]
        for extension in ("hea", "dat")
    ]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(
            executor.map(lambda name: _download_file(name, directory, base_url=base_url), filenames)
        )
    manifest.to_csv(directory / "manifest.csv", index=False)
    info = {
        "dataset": "PTB-XL",
        "version": VERSION,
        "source": base_url.rstrip("/") + "/",
        "dataset_url": DATASET_URL,
        "seed": seed,
        "per_single_class": per_class,
        "multilabel_count": multilabel_count,
        "records": len(manifest),
        "patients": int(manifest["patient_id"].nunique()),
        "frequency_hz": 100,
        "folds": sorted(manifest["strat_fold"].astype(int).unique().tolist()),
        "class_order": CLASSES,
        "stratum_counts": manifest["sampling_group"].value_counts().to_dict(),
        "metadata_sha256": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in METADATA_FILES
        },
        "interpretation": "Fixed-size diagnostic groups, sampled from training folds.",
    }
    (directory / "dataset_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
