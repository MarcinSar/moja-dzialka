"""
Logging utility functions for data pipeline.
"""

import sys
from pathlib import Path
from typing import Optional, Union
import pandas as pd
import geopandas as gpd

try:
    from loguru import logger
    LOGURU_AVAILABLE = True
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    LOGURU_AVAILABLE = False


def setup_logger(
    log_file: Optional[Union[str, Path]] = None,
    level: str = "INFO",
    rotation: str = "10 MB",
    retention: str = "7 days"
):
    """
    Setup loguru logger with file and console handlers.

    Args:
        log_file: Path to log file (optional)
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        rotation: Log rotation setting
        retention: Log retention setting

    Returns:
        Logger instance
    """
    if LOGURU_AVAILABLE:
        # Remove default handler
        logger.remove()

        # Add console handler with colors
        logger.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>",
            level=level,
            colorize=True
        )

        # Add file handler if specified
        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                log_file,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level=level,
                rotation=rotation,
                retention=retention,
                compression="zip"
            )

        return logger
    else:
        # Fallback to standard logging
        logging.basicConfig(
            level=getattr(logging, level),
            format="%(asctime)s | %(levelname)-8s | %(funcName)s - %(message)s",
            datefmt="%H:%M:%S"
        )

        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
            ))
            logging.getLogger().addHandler(file_handler)

        return logging.getLogger(__name__)


def log_dataframe_info(
    df: Union[pd.DataFrame, gpd.GeoDataFrame],
    name: str = "DataFrame",
    logger_instance=None
) -> None:
    """
    Log summary information about a DataFrame.

    Args:
        df: DataFrame or GeoDataFrame to summarize
        name: Name to use in log messages
        logger_instance: Logger to use (defaults to module logger)
    """
    log = logger_instance or logger

    log.info(f"=== {name} Summary ===")
    log.info(f"  Records: {len(df):,}")
    log.info(f"  Columns: {len(df.columns)}")

    # Memory usage
    memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
    log.info(f"  Memory: {memory_mb:.1f} MB")

    # Column info
    log.info(f"  Columns: {', '.join(df.columns[:10])}" +
             (f"... (+{len(df.columns) - 10} more)" if len(df.columns) > 10 else ""))

    # GeoDataFrame specific info
    if isinstance(df, gpd.GeoDataFrame):
        log.info(f"  CRS: {df.crs}")
        log.info(f"  Geometry type: {df.geometry.geom_type.value_counts().to_dict()}")
        log.info(f"  Bounds: {tuple(df.total_bounds)}")

        # Invalid geometries
        invalid = (~df.geometry.is_valid).sum()
        if invalid > 0:
            log.warning(f"  Invalid geometries: {invalid:,}")

        # Empty geometries
        empty = df.geometry.is_empty.sum()
        if empty > 0:
            log.warning(f"  Empty geometries: {empty:,}")

    # NULL values
    null_counts = df.isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    if len(cols_with_nulls) > 0:
        log.info(f"  Columns with NULLs: {len(cols_with_nulls)}")
        for col, count in cols_with_nulls.head(5).items():
            pct = count / len(df) * 100
            log.info(f"    - {col}: {count:,} ({pct:.1f}%)")


def log_processing_stats(
    input_count: int,
    output_count: int,
    operation: str,
    logger_instance=None
) -> None:
    """
    Log processing statistics.

    Args:
        input_count: Number of input records
        output_count: Number of output records
        operation: Name of the operation
        logger_instance: Logger to use
    """
    log = logger_instance or logger

    diff = output_count - input_count
    pct_change = (diff / input_count * 100) if input_count > 0 else 0

    log.info(f"{operation}: {input_count:,} -> {output_count:,} "
             f"({'+' if diff >= 0 else ''}{diff:,}, {pct_change:+.1f}%)")


def log_validation_result(
    name: str,
    passed: bool,
    value: Union[int, float, str],
    threshold: Optional[Union[int, float]] = None,
    logger_instance=None
) -> None:
    """
    Log a validation result.

    Args:
        name: Name of the validation check
        passed: Whether the check passed
        value: Actual value
        threshold: Expected threshold (optional)
        logger_instance: Logger to use
    """
    log = logger_instance or logger

    status = "PASS" if passed else "FAIL"
    threshold_str = f" (threshold: {threshold})" if threshold is not None else ""

    if passed:
        log.info(f"[{status}] {name}: {value}{threshold_str}")
    else:
        log.warning(f"[{status}] {name}: {value}{threshold_str}")


class ProgressLogger:
    """Simple progress logger for long operations."""

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        log_every: int = 10,
        logger_instance=None
    ):
        """
        Initialize progress logger.

        Args:
            total: Total number of items
            description: Description of the operation
            log_every: Log progress every N percent
            logger_instance: Logger to use
        """
        self.total = total
        self.description = description
        self.log_every = log_every
        self.log = logger_instance or logger
        self.current = 0
        self.last_logged_pct = -log_every

    def update(self, n: int = 1) -> None:
        """Update progress by n items."""
        self.current += n
        pct = (self.current / self.total * 100) if self.total > 0 else 100

        if pct >= self.last_logged_pct + self.log_every:
            self.log.info(f"{self.description}: {pct:.0f}% ({self.current:,}/{self.total:,})")
            self.last_logged_pct = int(pct / self.log_every) * self.log_every

    def finish(self) -> None:
        """Log completion."""
        self.log.info(f"{self.description}: Complete ({self.total:,} items)")
