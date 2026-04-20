"""Chart generation for the PDF report (volume histogram + category pie)."""

from __future__ import annotations

from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt

from heap_analyzer.report.palette import (
    category_color,
)
from heap_analyzer.utils.logging import get_stderr_logger

matplotlib.use("Agg")

logger = get_stderr_logger(__name__)


def render_volume_histogram(
    volumes: list[float],
    dpi: int = 150,
) -> bytes:
    """Render a histogram of heap volumes as a PNG.

    Args:
        volumes: List of volumes in m³.
        dpi: Output resolution.

    Returns:
        PNG image bytes.
    """
    fig, ax = plt.subplots(1, 1, figsize=(7, 4))

    if volumes:
        n_bins = min(10, max(3, len(volumes) // 2))
        ax.hist(
            volumes, bins=n_bins,
            color="#3b82f6", edgecolor="#1e40af",
            alpha=0.8,
        )
    else:
        ax.text(0.5, 0.5, "Nessun dato", ha="center", va="center", fontsize=12)

    ax.set_xlabel("Volume (m\u00b3)", fontsize=10)
    ax.set_ylabel("Numero cumuli", fontsize=10)
    ax.set_title("Distribuzione volumi", fontsize=12, fontweight="bold")
    ax.tick_params(labelsize=9)

    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def render_category_pie(
    category_volumes: dict[str | None, float],
    project_categories: list[str],
    dpi: int = 150,
) -> bytes:
    """Render a pie chart of material categories by total volume.

    Args:
        category_volumes: Mapping category -> total volume.
            None key = unclassified.
        project_categories: Ordered category list for coloring.
        dpi: Output resolution.

    Returns:
        PNG image bytes.
    """
    fig, ax = plt.subplots(1, 1, figsize=(7, 4.5))

    if not category_volumes or all(v == 0 for v in category_volumes.values()):
        ax.text(
            0.5, 0.5, "Nessuna classificazione disponibile",
            ha="center", va="center", fontsize=12, fontstyle="italic",
        )
        ax.axis("off")
    else:
        labels = []
        sizes = []
        colors = []

        for cat, vol in sorted(
            category_volumes.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            cat_label = cat if cat is not None else "Non classificato"
            labels.append(cat_label)
            sizes.append(vol)
            colors.append(category_color(cat, project_categories))

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=None,
            colors=colors,
            autopct=lambda pct: f"{pct:.1f}%" if pct > 3 else "",
            startangle=90,
            textprops={"fontsize": 9},
        )

        # Legend on the right
        ax.legend(
            wedges, labels,
            loc="center left",
            bbox_to_anchor=(1.0, 0.5),
            fontsize=9,
        )

        ax.set_title(
            "Categorie materiale (% volume)",
            fontsize=12, fontweight="bold",
        )

    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
