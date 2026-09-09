from mri_prep.datasets.adni import ADNIAdapter
from mri_prep.datasets.ppmi import PPMIAdapter

ADAPTERS = {
    "ppmi": PPMIAdapter,
    "adni": ADNIAdapter,
}


def get_adapter(name: str):
    if name not in ADAPTERS:
        raise ValueError(f"Unknown adapter '{name}'. Available: {sorted(ADAPTERS)}")
    return ADAPTERS[name]()
