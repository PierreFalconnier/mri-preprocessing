import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def parse_imaging_protocol(text):
    """Parse 'key=value;...' text into a dictionary."""
    if pd.isna(text):
        return {}

    parsed = {}
    for item in text.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Try converting to numeric
            try:
                value_numeric = pd.to_numeric(value)
                parsed[key] = value_numeric
            except ValueError:
                parsed[key] = value
    return parsed


def plot_bar(df, col, title=None, figsize=(6, 4), annotate=True):
    """
    Bar plot for categorical column with counts annotated on top.
    Includes missing values as 'Missing'.
    """
    if not title:
        title = f"Counts of {col}"

    counts = df[col].value_counts(dropna=False).sort_values(ascending=False)

    # Replace NaN index with "Missing"
    labels = counts.index.to_series().fillna("MISSING VALUES (NA)").astype(str)

    plt.figure(figsize=figsize)
    ax = sns.barplot(x=labels, y=counts.values, palette="viridis")

    plt.title(title)
    plt.xlabel(col)
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha="right")

    if annotate:
        for i, v in enumerate(counts.values):
            if v > 0:
                ax.text(i, v + 0.5, str(v), ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.show()


def plot_hist(df, col, title=None):
    if not title:
        title = f"Distribution of {col}"
    plt.figure(figsize=(6, 4))

    # Plot histogram
    ax = sns.histplot(df[col], bins=30, kde=False)  # disable KDE for counts clarity

    plt.title(title)
    plt.xlabel(col)
    plt.ylabel("Count")

    # Annotate counts on top of each bin
    for patch in ax.patches:
        height = patch.get_height()
        if height > 0:  # only annotate non-empty bins
            ax.text(
                patch.get_x() + patch.get_width() / 2,  # center of bin
                height + 0.5,  # slightly above the bar
                int(height),  # show integer count
                ha="center",
                va="bottom",
                fontsize=8,
            )

    plt.show()
