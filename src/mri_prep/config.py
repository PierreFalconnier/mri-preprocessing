"""Dataset configuration loading.

Every dataset (PPMI, ADNI, AABC, ...) is described by one YAML file in
``configs/datasets/``. The shared pipeline (BIDS conversion, preprocessing,
QC, export, tabular merge) reads paths and options from this config instead
of having them hardcoded in scripts, so adding a new dataset means writing a
config + a thin adapter, not copy-pasting a pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = REPO_ROOT / "configs" / "datasets"


class DatasetPaths(BaseModel):
    raw_dicom_root: Path | None = None
    flattened_root: Path | None = None
    bids_root: Path | None = None
    preprocessed_root: Path | None = None
    curated_root: Path | None = None
    csv_root: Path | None = None
    qc_csv: Path | None = None


class DatasetConfig(BaseModel):
    """Everything the generic pipeline needs to know about one dataset."""

    name: str
    adapter: str = Field(description="key of the dataset adapter, e.g. 'ppmi', 'adni', 'generic'")
    paths: DatasetPaths = DatasetPaths()
    template: Path | None = None
    template_mask: Path | None = None
    modality: str = "t1"
    extra: dict[str, Any] = Field(default_factory=dict)

    def resolved(self) -> "DatasetConfig":
        """Expand ``~`` and resolve relative paths against the repo root.

        Keeps configs portable: relative paths are anchored to the repo
        (not the current working directory), absolute paths and ``~/...``
        paths are left as machine-specific overrides.
        """
        data = self.model_dump()

        def _resolve(value: str | None) -> str | None:
            if value is None:
                return None
            p = Path(value).expanduser()
            if not p.is_absolute():
                p = (REPO_ROOT / p).resolve()
            return str(p)

        for key, value in data["paths"].items():
            data["paths"][key] = _resolve(value)
        data["template"] = _resolve(data.get("template"))
        data["template_mask"] = _resolve(data.get("template_mask"))
        return DatasetConfig(**data)


def list_datasets() -> list[str]:
    return sorted(p.stem for p in CONFIGS_DIR.glob("*.yaml"))


def load_dataset_config(name: str) -> DatasetConfig:
    path = CONFIGS_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(list_datasets()) or "(none found)"
        raise FileNotFoundError(
            f"No config for dataset '{name}' at {path}. Available: {available}"
        )
    with open(path) as f:
        raw = yaml.safe_load(f)
    return DatasetConfig(**raw).resolved()
