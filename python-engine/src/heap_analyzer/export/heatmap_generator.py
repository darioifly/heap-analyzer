"""Generate colored PNG heatmap from nDSM raster."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def generate_ndsm_heatmap(
    ndsm_path: Path,
    output_path: Path,
    colormap: str = "turbo",
    height_threshold: float = 0.5,
) -> Path:
    """Generate colored PNG visualization of nDSM.

    Below threshold = transparent. Above threshold = colored using matplotlib colormap.

    Args:
        ndsm_path: Path to nDSM GeoTIFF.
        output_path: Output PNG path.
        colormap: Matplotlib colormap name.
        height_threshold: Height below which pixels are transparent.

    Returns:
        Path to the generated PNG.
    """
    import matplotlib.cm as cm

    with rasterio.open(str(ndsm_path)) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata

    # Mask nodata
    if nodata is not None:
        data[data == nodata] = 0.0

    # Create alpha mask: transparent where below threshold
    mask = data >= height_threshold

    # Normalize values to 0-1 range for colormap
    valid = data[mask]
    if len(valid) == 0:
        # No values above threshold — save fully transparent image
        rgba = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
        Image.fromarray(rgba, "RGBA").save(str(output_path), "PNG")
        return output_path

    vmin = height_threshold
    vmax = float(np.max(valid))
    if vmax <= vmin:
        vmax = vmin + 1.0

    normalized = np.clip((data - vmin) / (vmax - vmin), 0, 1)

    # Apply colormap
    cmap = cm.get_cmap(colormap)
    colored = (cmap(normalized) * 255).astype(np.uint8)  # (H, W, 4)

    # Set alpha: 0 where below threshold, 255 where above
    colored[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(colored, "RGBA").save(str(output_path), "PNG")

    return output_path
