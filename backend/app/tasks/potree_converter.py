"""
PotreeConverter 2.0 wrapper for converting LAZ files to Potree format.

PotreeConverter 2.0 generates optimized octree structure for web visualization.
Output format: hierarchy.bin + octree.bin (much simpler than v1.7)

Documentation: https://github.com/potree/PotreeConverter
"""

import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

# Default PotreeConverter path
POTREE_CONVERTER_PATH = os.getenv("POTREE_CONVERTER_PATH", "PotreeConverter")

# Conversion settings
DEFAULT_SETTINGS = {
    # Output format (LAS is more compatible than LAZ for Potree)
    "encoding": "DEFAULT",
    # Generate LOD (Level of Detail)
    "generate-page": True,
    # Method for point distribution
    "method": "poisson",
}


class PotreeConversionError(Exception):
    """Raised when PotreeConverter fails."""
    pass


async def convert_laz_to_potree(
    laz_path: Path,
    output_path: Path,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    parcel_bbox: Optional[tuple] = None,
) -> Path:
    """
    Convert LAZ file to Potree 2.0 format.

    Args:
        laz_path: Path to input LAZ file
        output_path: Directory for Potree output
        progress_callback: Optional callback(progress: 70-100, message: str)
        parcel_bbox: Optional (min_x, min_y, max_x, max_y) to crop to parcel area

    Returns:
        Path to Potree output directory (contains metadata.json, hierarchy.bin, octree.bin)

    Raises:
        PotreeConversionError: If conversion fails
    """
    laz_path = Path(laz_path)
    output_path = Path(output_path)

    if not laz_path.exists():
        raise PotreeConversionError(f"LAZ file not found: {laz_path}")

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)

    # Check if already converted
    metadata_file = output_path / "metadata.json"
    if metadata_file.exists():
        logger.info(f"Potree already exists: {output_path}")
        if progress_callback:
            progress_callback(100.0, "Dane Potree już istnieją w cache")
        return output_path

    logger.info(f"Converting {laz_path} to Potree format...")
    if progress_callback:
        progress_callback(72.0, "Konwertuję do formatu Potree...")

    # Build PotreeConverter command
    cmd = [
        POTREE_CONVERTER_PATH,
        str(laz_path),
        "-o", str(output_path),
    ]

    # Add bounding box filter if specified (crop to parcel area + buffer)
    if parcel_bbox:
        min_x, min_y, max_x, max_y = parcel_bbox
        # Add 50m buffer around parcel
        buffer = 50
        cmd.extend([
            "--aabb",
            f"{min_x - buffer},{min_y - buffer},{0}",
            f"{max_x + buffer},{max_y + buffer},{1000}",
        ])

    logger.debug(f"Running command: {' '.join(cmd)}")

    try:
        # Run PotreeConverter as subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Monitor progress from stdout
        stdout_lines = []
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode().strip()
            stdout_lines.append(line_str)
            logger.debug(f"PotreeConverter: {line_str}")

            # Parse progress from output
            if progress_callback:
                progress = _parse_progress(line_str)
                if progress:
                    # Map 0-100 from converter to 72-98 range
                    mapped_progress = 72 + (progress * 0.26)
                    progress_callback(mapped_progress, f"Konwersja: {progress:.0f}%")

        # Wait for completion
        await process.wait()

        if process.returncode != 0:
            stderr = await process.stderr.read()
            error_msg = stderr.decode() if stderr else "\n".join(stdout_lines[-10:])
            raise PotreeConversionError(
                f"PotreeConverter failed with code {process.returncode}: {error_msg}"
            )

        # Verify output
        if not metadata_file.exists():
            raise PotreeConversionError(
                f"Conversion completed but metadata.json not found in {output_path}"
            )

        if progress_callback:
            progress_callback(98.0, "Finalizuję konwersję...")

        logger.info(f"Potree conversion complete: {output_path}")
        return output_path

    except FileNotFoundError:
        raise PotreeConversionError(
            f"PotreeConverter not found at {POTREE_CONVERTER_PATH}. "
            "Make sure it's installed and in PATH."
        )


def _parse_progress(line: str) -> Optional[float]:
    """
    Parse progress percentage from PotreeConverter output.

    Output format varies by version, common patterns:
    - "indexing: 50%"
    - "Progress: 75%"
    - "50.00%"
    """
    patterns = [
        r"(\d+(?:\.\d+)?)\s*%",  # Generic percentage
        r"indexing:\s*(\d+(?:\.\d+)?)",
        r"progress:\s*(\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return float(match.group(1))

    return None


def check_potree_converter() -> bool:
    """Check if PotreeConverter is available."""
    try:
        result = subprocess.run(
            [POTREE_CONVERTER_PATH, "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_potree_info(output_path: Path) -> dict:
    """
    Get information about converted Potree data.

    Returns:
        Dictionary with point count, bounds, etc.
    """
    import json

    metadata_file = output_path / "metadata.json"
    if not metadata_file.exists():
        return {}

    with open(metadata_file) as f:
        metadata = json.load(f)

    return {
        "version": metadata.get("version", "unknown"),
        "points": metadata.get("points", 0),
        "bounds": metadata.get("boundingBox", {}),
        "spacing": metadata.get("spacing", 0),
        "scale": metadata.get("scale", 1.0),
    }


def cleanup_potree_output(output_path: Path) -> None:
    """Remove Potree output directory."""
    if output_path.exists():
        shutil.rmtree(output_path)
        logger.info(f"Removed Potree output: {output_path}")
