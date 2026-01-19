"""
Celery configuration for moja-dzialka background tasks.

Main use case: LiDAR data processing pipeline
- Download LAZ files from GUGiK
- Convert to Potree format using PotreeConverter 2.0
- Notify frontend via Redis pub/sub
"""

import os
from celery import Celery

# Redis connection from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Create Celery app
celery_app = Celery(
    "moja_dzialka",
    broker=f"{REDIS_URL}/0",
    backend=f"{REDIS_URL}/1",
    include=[
        "app.tasks.lidar_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Warsaw",
    enable_utc=True,

    # Task execution
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time for LiDAR processing

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # Task routing
    task_routes={
        "app.tasks.lidar_tasks.*": {"queue": "lidar"},
    },

    # Rate limits (don't overwhelm GUGiK servers)
    task_default_rate_limit="10/m",

    # Retry settings
    task_default_retry_delay=30,
    task_max_retries=3,
)

# Beat schedule for periodic tasks (cache cleanup)
celery_app.conf.beat_schedule = {
    "cleanup-lidar-cache": {
        "task": "app.tasks.lidar_tasks.cleanup_lidar_cache",
        "schedule": 6 * 60 * 60,  # Every 6 hours
    },
}
