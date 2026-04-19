"""Spatial matching of heaps between two surveys using Hungarian algorithm.

Algorithm (see docs/decisions/F6-matching-algorithm.md):
  1. Build IoU cost matrix C[i,j] = -iou(a_i, b_j).
  2. Run scipy.optimize.linear_sum_assignment (Hungarian) for global optimum.
  3. Filter assignments by iou_threshold; classify state.
  4. Post-hoc ambiguity detection from the raw IoU matrix.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel
from scipy.optimize import linear_sum_assignment
from shapely import make_valid
from shapely.geometry import MultiPolygon
from shapely.geometry import shape as shapely_shape

from heap_analyzer.comparison.config import ComparisonConfig
from heap_analyzer.comparison.palette import ComparisonState
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


# ---------------------------------------------------------------------------
# Input record — what the matcher needs per heap
# ---------------------------------------------------------------------------

class HeapRecord(BaseModel):
    """Minimal heap record for matching."""

    heap_id: int
    polygon_geojson: dict  # type: ignore[type-arg]
    volume_m3: float
    planimetric_area_m2: float
    max_height_m: float


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class HeapMatch(BaseModel):
    """A single matched heap pair."""

    heap_a_id: int
    heap_b_id: int
    iou: float
    state: ComparisonState
    delta_volume: float
    delta_planimetric_area: float
    delta_max_height: float
    delta_volume_percent: float
    a_candidates: list[int] = []
    b_candidates: list[int] = []


class MatchSummary(BaseModel):
    """Counts by comparison state."""

    unchanged: int = 0
    grown: int = 0
    decreased: int = 0
    added: int = 0
    removed: int = 0
    ambiguous: int = 0


class MatchResult(BaseModel):
    """Complete matching result."""

    matched: list[HeapMatch]
    removed_in_a: list[int]
    added_in_b: list[int]
    total_delta_volume: float
    total_delta_volume_percent: float
    volume_a: float
    volume_b: float
    config: ComparisonConfig
    summary: MatchSummary


# ---------------------------------------------------------------------------
# Matching algorithm
# ---------------------------------------------------------------------------

def _to_valid_geometry(geojson: dict) -> MultiPolygon | None:  # type: ignore[type-arg]
    """Convert GeoJSON to a valid shapely geometry.

    Returns None if the geometry is empty or unrecoverable.
    """
    try:
        geom = shapely_shape(geojson)
    except Exception:  # noqa: BLE001
        return None

    if not geom.is_valid:
        geom = make_valid(geom)

    if geom.is_empty:
        return None

    # Normalize to Polygon/MultiPolygon
    if geom.geom_type == "GeometryCollection":
        # Take largest polygon from collection
        polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        if not polys:
            return None
        geom = max(polys, key=lambda g: g.area)

    return geom


def _compute_iou_matrix(
    geoms_a: list,  # type: ignore[type-arg]
    geoms_b: list,  # type: ignore[type-arg]
) -> np.ndarray:
    """Compute IoU matrix between two lists of geometries.

    Returns:
        2D array of shape (len(geoms_a), len(geoms_b)).
    """
    n_a = len(geoms_a)
    n_b = len(geoms_b)
    iou_matrix = np.zeros((n_a, n_b), dtype=np.float64)

    for i in range(n_a):
        ga = geoms_a[i]
        if ga is None:
            continue
        for j in range(n_b):
            gb = geoms_b[j]
            if gb is None:
                continue
            try:
                inter = ga.intersection(gb).area
                if inter <= 0:
                    continue
                union = ga.union(gb).area
                if union > 0:
                    iou_matrix[i, j] = inter / union
            except Exception:  # noqa: BLE001
                logger.warning("IoU computation failed for pair (%d, %d)", i, j)

    return iou_matrix


def match_heaps(
    heaps_a: list[HeapRecord],
    heaps_b: list[HeapRecord],
    config: ComparisonConfig | None = None,
) -> MatchResult:
    """Match heaps between survey A and survey B.

    Uses Hungarian algorithm for globally optimal IoU-based assignment,
    followed by post-hoc ambiguity detection.

    Args:
        heaps_a: Heaps from survey A (baseline).
        heaps_b: Heaps from survey B (comparison target).
        config: Matching configuration. Uses defaults if None.

    Returns:
        MatchResult with matched pairs, removed, added, and summary.
    """
    if config is None:
        config = ComparisonConfig()

    # Convert polygons to shapely geometries
    geoms_a = [_to_valid_geometry(h.polygon_geojson) for h in heaps_a]
    geoms_b = [_to_valid_geometry(h.polygon_geojson) for h in heaps_b]

    n_a = len(heaps_a)
    n_b = len(heaps_b)

    volume_a = sum(h.volume_m3 for h in heaps_a)
    volume_b = sum(h.volume_m3 for h in heaps_b)

    # Edge case: empty inputs
    if n_a == 0 and n_b == 0:
        return MatchResult(
            matched=[],
            removed_in_a=[],
            added_in_b=[],
            total_delta_volume=0.0,
            total_delta_volume_percent=0.0,
            volume_a=0.0,
            volume_b=0.0,
            config=config,
            summary=MatchSummary(),
        )

    if n_a == 0:
        return MatchResult(
            matched=[],
            removed_in_a=[],
            added_in_b=[h.heap_id for h in heaps_b],
            total_delta_volume=volume_b,
            total_delta_volume_percent=100.0,
            volume_a=0.0,
            volume_b=volume_b,
            config=config,
            summary=MatchSummary(added=n_b),
        )

    if n_b == 0:
        return MatchResult(
            matched=[],
            removed_in_a=[h.heap_id for h in heaps_a],
            added_in_b=[],
            total_delta_volume=-volume_a,
            total_delta_volume_percent=-100.0,
            volume_a=volume_a,
            volume_b=0.0,
            config=config,
            summary=MatchSummary(removed=n_a),
        )

    # Step 1: Compute IoU matrix
    iou_matrix = _compute_iou_matrix(geoms_a, geoms_b)

    # Step 2: Hungarian assignment (minimize -IoU = maximize IoU)
    cost_matrix = -iou_matrix
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    # Step 3: Build matched pairs, filter by threshold
    matched: list[HeapMatch] = []
    matched_a_indices: set[int] = set()
    matched_b_indices: set[int] = set()

    for row_idx, col_idx in zip(row_indices, col_indices, strict=True):
        iou_val = float(iou_matrix[row_idx, col_idx])
        if iou_val < config.iou_threshold:
            continue  # below threshold — not a match

        ha = heaps_a[row_idx]
        hb = heaps_b[col_idx]

        delta_vol = hb.volume_m3 - ha.volume_m3
        delta_area = hb.planimetric_area_m2 - ha.planimetric_area_m2
        delta_height = hb.max_height_m - ha.max_height_m
        delta_vol_pct = (delta_vol / ha.volume_m3 * 100) if ha.volume_m3 > 0 else 0.0

        # Classify state
        if abs(delta_vol_pct) / 100 < config.stability_threshold:
            state: ComparisonState = "unchanged"
        elif delta_vol > 0:
            state = "grown"
        else:
            state = "decreased"

        matched.append(HeapMatch(
            heap_a_id=ha.heap_id,
            heap_b_id=hb.heap_id,
            iou=round(iou_val, 4),
            state=state,
            delta_volume=round(delta_vol, 3),
            delta_planimetric_area=round(delta_area, 3),
            delta_max_height=round(delta_height, 3),
            delta_volume_percent=round(delta_vol_pct, 2),
        ))

        matched_a_indices.add(row_idx)
        matched_b_indices.add(col_idx)

    # Step 4: Identify removed (only in A) and added (only in B)
    removed_in_a = [
        heaps_a[i].heap_id for i in range(n_a) if i not in matched_a_indices
    ]
    added_in_b = [
        heaps_b[j].heap_id for j in range(n_b) if j not in matched_b_indices
    ]

    # Step 5: Ambiguity detection (separate pass on raw IoU matrix)
    # For each A heap, find all B heaps above threshold; vice versa
    a_id_to_idx = {heaps_a[i].heap_id: i for i in range(n_a)}
    b_id_to_idx = {heaps_b[j].heap_id: j for j in range(n_b)}

    for match in matched:
        a_idx = a_id_to_idx[match.heap_a_id]
        b_idx = b_id_to_idx[match.heap_b_id]

        # Other B candidates for this A heap
        other_b = [
            heaps_b[j].heap_id
            for j in range(n_b)
            if j != b_idx and iou_matrix[a_idx, j] >= config.iou_threshold
        ]

        # Other A candidates for this B heap
        other_a = [
            heaps_a[i].heap_id
            for i in range(n_a)
            if i != a_idx and iou_matrix[i, b_idx] >= config.iou_threshold
        ]

        if other_b or other_a:
            match.state = "ambiguous"
            match.a_candidates = other_b  # B heaps that also overlap A
            match.b_candidates = other_a  # A heaps that also overlap B

    # Step 6: Build summary
    summary = MatchSummary(
        unchanged=sum(1 for m in matched if m.state == "unchanged"),
        grown=sum(1 for m in matched if m.state == "grown"),
        decreased=sum(1 for m in matched if m.state == "decreased"),
        ambiguous=sum(1 for m in matched if m.state == "ambiguous"),
        added=len(added_in_b),
        removed=len(removed_in_a),
    )

    # Total delta volume (matched deltas + added volumes - removed volumes)
    matched_delta = sum(m.delta_volume for m in matched)
    added_vol = sum(hb.volume_m3 for hb in heaps_b if hb.heap_id in added_in_b)
    removed_vol = sum(ha.volume_m3 for ha in heaps_a if ha.heap_id in removed_in_a)
    total_delta = matched_delta + added_vol - removed_vol
    total_delta_pct = (total_delta / volume_a * 100) if volume_a > 0 else 0.0

    logger.debug(
        "Matching complete: %d matched, %d removed, %d added, delta=%.1f m³ (%.1f%%)",
        len(matched), len(removed_in_a), len(added_in_b),
        total_delta, total_delta_pct,
    )

    return MatchResult(
        matched=matched,
        removed_in_a=removed_in_a,
        added_in_b=added_in_b,
        total_delta_volume=round(total_delta, 3),
        total_delta_volume_percent=round(total_delta_pct, 2),
        volume_a=round(volume_a, 3),
        volume_b=round(volume_b, 3),
        config=config,
        summary=summary,
    )
