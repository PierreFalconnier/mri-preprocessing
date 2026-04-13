# Core
# import datetime
import math

# Plotting
import matplotlib.pyplot as plt

# Neuroimaging
import numpy as np

# Data handling
import pandas as pd


def plot_histograms_grid(
    df,
    keys,
    bins=30,
    dropna=True,
    max_cols=4,
    figsize_per_plot=(4, 3),
    percentile_low=1,
    percentile_high=99,
):
    """
    Plot histograms for multiple dataframe columns in a single figure,
    with percentile markers for numeric variables.
    """

    keys = [k for k in keys if k in df.columns]
    if not keys:
        raise ValueError("None of the provided keys exist in the dataframe")

    n = len(keys)
    n_cols = min(max_cols, n)
    n_rows = math.ceil(n / n_cols)

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(figsize_per_plot[0] * n_cols, figsize_per_plot[1] * n_rows),
        squeeze=False,
    )

    axes = axes.flatten()

    for ax, key in zip(axes, keys):
        data = df[key]

        if dropna:
            data = data.dropna()

        if data.empty:
            ax.set_title(f"{key} (no data)")
            ax.axis("off")
            continue

        # Try numeric conversion
        is_numeric = True
        try:
            data = pd.to_numeric(data)
        except Exception:
            is_numeric = False

        if is_numeric:
            values = data.values

            ax.hist(values, bins=min(bins, len(values)))
            ax.set_ylabel("Count")

            # Percentiles
            p_low = np.percentile(values, percentile_low)
            p_high = np.percentile(values, percentile_high)

            ax.axvline(p_low, linestyle="--", linewidth=1)
            ax.axvline(p_high, linestyle="--", linewidth=1)

            ax.text(
                p_low,
                ax.get_ylim()[1] * 0.9,
                f"{percentile_low}%",
                rotation=90,
                va="top",
                ha="right",
            )
            ax.text(
                p_high,
                ax.get_ylim()[1] * 0.9,
                f"{percentile_high}%",
                rotation=90,
                va="top",
                ha="left",
            )

        else:
            counts = data.value_counts()
            ax.bar(counts.index.astype(str), counts.values)
            ax.tick_params(axis="x", rotation=45)

        ax.set_title(key)
        ax.grid(True, alpha=0.3)

    # Hide unused subplots
    for ax in axes[len(keys) :]:
        ax.axis("off")

    fig.tight_layout()
    plt.show()


def plot_histogram(df, key, bins=20, dropna=True, eps=1e-8):
    if key not in df.columns:
        raise ValueError(f"Key '{key}' not found in dataframe")

    data = df[key]

    if dropna:
        data = data.dropna()

    if len(data) == 0:
        print(f"[WARN] No data available for '{key}'")
        return

    # Attempt numeric conversion
    is_numeric = True
    try:
        data = pd.to_numeric(data)
    except (ValueError, TypeError):
        is_numeric = False

    plt.figure()

    if is_numeric:
        data_min = data.min()
        data_max = data.max()

        # Zero or near-zero range → constant value
        if np.isclose(data_min, data_max, atol=eps):
            plt.bar([str(round(float(data_min), 4))], [len(data)])
            plt.xlabel(key)
            plt.ylabel("Count")
            plt.title(f"{key} (constant value)")
        else:
            # Safe bin count
            effective_bins = min(bins, len(data))
            plt.hist(data, bins=effective_bins)
            plt.xlabel(key)
            plt.ylabel("Count")
            plt.title(f"Histogram of {key}")
    else:
        # Categorical fallback
        counts = data.value_counts()
        plt.bar(counts.index.astype(str), counts.values)
        plt.xlabel(key)
        plt.ylabel("Count")
        plt.title(f"Distribution of {key}")
        plt.xticks(rotation=45, ha="right")

    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
