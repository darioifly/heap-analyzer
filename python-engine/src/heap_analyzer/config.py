"""Processing configuration with Pydantic validation."""

from pathlib import Path

from pydantic import BaseModel, Field


class ProcessingConfig(BaseModel):
    """Configuration parameters for heap detection and volumetric processing.

    All defaults match SPEC.md [CONFIG].
    """

    dsm_resolution: float = Field(default=0.10, description="DSM resolution in meters/pixel")
    height_threshold: float = Field(
        default=0.5, description="Minimum nDSM height in meters to consider as heap"
    )
    min_heap_area: float = Field(
        default=50.0, description="Minimum heap area in m² (below = excluded)"
    )
    max_heap_area: float = Field(
        default=50000.0, description="Maximum heap area in m² (above = flagged for review)"
    )
    base_percentile: float = Field(
        default=5.0, description="Percentile for terrain estimation from peripheral zones"
    )
    morpho_kernel_size: int = Field(
        default=50,
        description="Morphological kernel size in pixels (= 5m @ 0.10m/px)",
    )
    precomputed_dsm_path: Path | None = Field(
        default=None,
        description=(
            "Optional path to a pre-generated DSM GeoTIFF. When set and the file "
            "exists, the pipeline copies it as the survey DSM and skips the DSM "
            "generation phase (used by DJI Terra import to reuse map/dsm.tif)."
        ),
    )
    ground_classification_opening_m: float = Field(
        default=60.0,
        description=(
            "Kernel size in meters for the morphological opening applied to the "
            "ASPRS class=2 DTM raster. Must exceed the widest heap (DJI Terra "
            "tends to misclassify pile tops as ground). Set to 0 to disable."
        ),
    )
