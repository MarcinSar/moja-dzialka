"""
ProfileManager - Load/save/update user profiles.

Uses Redis (hot, 7d TTL) and PostgreSQL (permanent) via persistence backend.
"""

from __future__ import annotations

import json
from typing import Optional, Dict, Any
from datetime import datetime

from loguru import logger

from app.profile.user_profile import UserProfile
from app.services.database import redis_cache


PROFILE_PREFIX = "profile:"
PROFILE_TTL = 7 * 24 * 3600  # 7 days


class ProfileManager:
    """Manages user profile lifecycle."""

    async def load(self, user_id: str) -> UserProfile:
        """Load profile from Redis, or create new one."""
        try:
            data = await redis_cache.get(f"{PROFILE_PREFIX}{user_id}")
            if data:
                profile = UserProfile.from_dict(json.loads(data))
                logger.debug(f"Loaded profile for {user_id} (sessions: {profile.session_count})")
                return profile
        except Exception as e:
            logger.warning(f"Failed to load profile from Redis: {e}")

        # Create new profile
        profile = UserProfile(
            user_id=user_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        logger.info(f"Created new profile for {user_id}")
        return profile

    async def save(self, profile: UserProfile) -> None:
        """Save profile to Redis."""
        try:
            profile.updated_at = datetime.now().isoformat()
            data = json.dumps(profile.to_dict(), ensure_ascii=False)
            await redis_cache.set(
                f"{PROFILE_PREFIX}{profile.user_id}",
                data,
                expire=PROFILE_TTL,
            )
            logger.debug(f"Saved profile for {profile.user_id}")
        except Exception as e:
            logger.warning(f"Failed to save profile to Redis: {e}")

    async def finalize_session(self, user_id: str, notepad_dict: Dict[str, Any]) -> None:
        """Merge session data into profile and save.

        Called when a session ends (user disconnects or explicit finalize).
        """
        profile = await self.load(user_id)
        profile.merge_session_data(notepad_dict)
        await self.save(profile)
        logger.info(f"Finalized session for {user_id} (total sessions: {profile.session_count})")
