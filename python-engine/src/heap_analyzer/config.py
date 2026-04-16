"""Processing configuration with Pydantic validation."""

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
