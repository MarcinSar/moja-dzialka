"""
Result Store - JSONL file management for search results.

Search results are written to JSONL files (one JSON object per line).
Agent paginates through results using results_load_page tool.
"""

import json
import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from loguru import logger


RESULTS_DIR = "/tmp/moja-dzialka/results"


def ensure_results_dir() -> str:
    """Ensure results directory exists."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return RESULTS_DIR


def write_results(results: List[Dict[str, Any]], session_id: str) -> str:
    """Write search results to JSONL file.

    Args:
        results: List of parcel result dicts
        session_id: Session identifier for namespacing

    Returns:
        Path to the JSONL file
    """
    ensure_results_dir()
    filename = f"{session_id}_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}.jsonl"
    filepath = os.path.join(RESULTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")

    logger.info(f"Wrote {len(results)} results to {filepath}")
    return filepath


def read_page(filepath: str, page: int = 0, page_size: int = 10) -> Dict[str, Any]:
    """Read a page of results from JSONL file.

    Args:
        filepath: Path to JSONL file
        page: 0-based page number
        page_size: Results per page

    Returns:
        Dict with items, page info, total count
    """
    if not os.path.exists(filepath):
        return {"error": f"Results file not found: {filepath}", "items": [], "total": 0}

    all_items = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_items.append(json.loads(line))

    total = len(all_items)
    start = page * page_size
    end = start + page_size
    items = all_items[start:end]

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "has_next": end < total,
        "has_prev": page > 0,
    }


def cleanup_old_results(max_age_hours: int = 24) -> int:
    """Remove result files older than max_age_hours.

    Returns:
        Number of files removed
    """
    ensure_results_dir()
    now = datetime.now().timestamp()
    removed = 0
    for filename in os.listdir(RESULTS_DIR):
        filepath = os.path.join(RESULTS_DIR, filename)
        if os.path.isfile(filepath):
            age_hours = (now - os.path.getmtime(filepath)) / 3600
            if age_hours > max_age_hours:
                os.remove(filepath)
                removed += 1
    if removed:
        logger.info(f"Cleaned up {removed} old result files")
    return removed
