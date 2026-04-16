"""CSV export for heap metrics per SPEC.md [EXPORT].

Format:
- Separator: `;` (semicolon — Italian Excel default)
- Encoding: UTF-8 with BOM (so Excel detects encoding)
- Decimal: `.` (point)
- Columns: Italian headers, order per SPEC
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from heap_analyzer.processing.volume import HeapMetrics
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)

# Italian column headers — order per SPEC.md [EXPORT] CSV
CSV_HEADERS = [
    "ID",
    "Volume_m3",
    "Area_planimetrica_m2",
    "Area_superficiale_m2",
    "Altezza_max_m",
    "Altezza_media_m",
    "Quota_base_mslm",
    "Centroide_E",
    "Centroide_N",
    "BBox_minE",
    "BBox_minN",
    "BBox_maxE",
    "BBox_maxN",
    "Categoria_materiale",
    "Data_rilievo",
]


def export_csv(
    heap_metrics: list[HeapMetrics],
    survey_metadata: dict[str, Any],
    output_path: Path,
    material_categories: dict[int, str] | None = None,
) -> Path:
    """Write CSV per SPEC.md [EXPORT] CSV format.

    Args:
        heap_metrics: List of heap metrics to export.
        survey_metadata: Must have "survey_date" key (ISO string or any string).
        output_path: Path for the output CSV file.
        material_categories: Optional mapping heap_id -> category name.

    Returns:
        output_path (same as input, for convenience).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    survey_date = survey_metadata.get("survey_date", "")
    categories = material_categories or {}

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(CSV_HEADERS)

        for m in heap_metrics:
            row = [
                m.heap_id,
                f"{m.volume_m3:.3f}",
                f"{m.planimetric_area_m2:.3f}",
                f"{m.surface_area_m2:.3f}",
                f"{m.max_height_m:.2f}",
                f"{m.mean_height_m:.2f}",
                f"{m.base_elevation_m:.2f}",
                f"{m.centroid_e:.6f}",
                f"{m.centroid_n:.6f}",
                f"{m.bbox_min_e:.6f}",
                f"{m.bbox_min_n:.6f}",
                f"{m.bbox_max_e:.6f}",
                f"{m.bbox_max_n:.6f}",
                categories.get(m.heap_id, ""),
                survey_date,
            ]
            writer.writerow(row)

    logger.debug("CSV exported: %s (%d heaps)", output_path, len(heap_metrics))
    return output_path
