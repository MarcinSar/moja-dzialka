"""
Workspace Manager - File-based user workspace (OpenClaw pattern).

Provides persistent file storage for user profiles and session archives.
This is TIER 4 (Cold) in the 5-tier memory architecture:
  TIER 1: Immediate (in-memory) - Working state
  TIER 2: Hot (Redis, <10ms) - Active sessions
  TIER 3: Warm (PostgreSQL, <100ms) - Full state, analytics
  TIER 4: Cold (Files, <500ms) - Session archives, patterns ← THIS
  TIER 5: Knowledge (Neo4j+SQLite) - Domain knowledge, embeddings
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import yaml

from loguru import logger
from pydantic import BaseModel

from app.memory.schemas.semantic import BuyerProfile, SemanticMemory


# Default workspace root (can be overridden via env)
DEFAULT_WORKSPACE_ROOT = os.path.expanduser("~/.parcela")


class WorkspaceConfig(BaseModel):
    """Configuration for workspace manager."""
    root_path: str = DEFAULT_WORKSPACE_ROOT
    create_if_missing: bool = True


class UserWorkspace:
    """Manages a single user's workspace directory.

    Structure:
        ~/.parcela/users/{user_id}/
        ├── profile.md           # User profile (markdown with YAML frontmatter)
        ├── profile.json         # Profile backup (structured)
        ├── sessions/
        │   ├── 2026-02-02_abc123.jsonl  # Session transcript
        │   └── ...
        └── memory/
            ├── 2026-02-02.md    # Daily memory extracts
            └── patterns.json    # Search patterns over time
    """

    def __init__(self, user_id: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT):
        self.user_id = user_id
        self.root = Path(workspace_root)
        self.user_dir = self.root / "users" / user_id

        # Sub-directories
        self.sessions_dir = self.user_dir / "sessions"
        self.memory_dir = self.user_dir / "memory"

    def ensure_exists(self) -> None:
        """Create workspace directories if they don't exist."""
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        logger.debug(f"Ensured workspace exists for user {self.user_id}")

    def exists(self) -> bool:
        """Check if user workspace exists."""
        return self.user_dir.exists()

    # =========================================================================
    # PROFILE MANAGEMENT (Markdown + YAML frontmatter)
    # =========================================================================

    @property
    def profile_path(self) -> Path:
        return self.user_dir / "profile.md"

    @property
    def profile_json_path(self) -> Path:
        return self.user_dir / "profile.json"

    def save_profile(self, profile: BuyerProfile) -> None:
        """Save user profile to both markdown and JSON formats."""
        self.ensure_exists()

        # Save JSON backup
        profile_dict = profile.model_dump(exclude_none=True)
        profile_dict["_updated_at"] = datetime.utcnow().isoformat()

        with open(self.profile_json_path, "w", encoding="utf-8") as f:
            json.dump(profile_dict, f, ensure_ascii=False, indent=2, default=str)

        # Save markdown with YAML frontmatter
        markdown_content = self._profile_to_markdown(profile)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.debug(f"Saved profile for user {self.user_id}")

    def load_profile(self) -> Optional[BuyerProfile]:
        """Load user profile from JSON (primary) or markdown (fallback)."""
        # Try JSON first (faster, more reliable)
        if self.profile_json_path.exists():
            try:
                with open(self.profile_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Remove metadata fields
                    data.pop("_updated_at", None)
                    return BuyerProfile.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to load JSON profile: {e}")

        # Fallback to markdown
        if self.profile_path.exists():
            try:
                return self._markdown_to_profile(self.profile_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to load markdown profile: {e}")

        return None

    def _profile_to_markdown(self, profile: BuyerProfile) -> str:
        """Convert profile to markdown with YAML frontmatter."""
        # Build YAML frontmatter
        frontmatter = {
            "name": profile.name,
            "contact_email": profile.contact_email,
            "contact_phone": profile.contact_phone,
            "budget": {
                "min": profile.budget_min,
                "max": profile.budget_max,
                "confidence": profile.budget_confidence,
            } if profile.budget_min or profile.budget_max else None,
            "size_m2": {
                "min": profile.size_m2_min,
                "max": profile.size_m2_max,
                "category": profile.preferred_size_category,
            } if profile.size_m2_min or profile.size_m2_max else None,
            "location": {
                "cities": profile.preferred_cities,
                "districts": profile.preferred_districts,
                "avoided": profile.avoided_districts,
            } if profile.preferred_cities or profile.preferred_districts else None,
            "priorities": {
                "quietness": profile.priority_quietness,
                "nature": profile.priority_nature,
                "accessibility": profile.priority_accessibility,
                "schools": profile.priority_schools,
                "transport": profile.priority_transport,
                "shops": profile.priority_shops,
            },
            "purpose": profile.purpose,
            "building_plans": profile.building_plans,
            "urgency": profile.urgency,
            "purchase_horizon": profile.purchase_horizon,
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Remove None values
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}

        yaml_content = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Build markdown body
        body_parts = ["# Profil Użytkownika\n"]

        if profile.name:
            body_parts.append(f"**Imię:** {profile.name}\n")

        if profile.preferred_cities:
            body_parts.append(f"\n## Preferowane lokalizacje\n")
            body_parts.append(f"- Miasta: {', '.join(profile.preferred_cities)}\n")
            if profile.preferred_districts:
                body_parts.append(f"- Dzielnice: {', '.join(profile.preferred_districts)}\n")

        if profile.budget_max:
            body_parts.append(f"\n## Budżet\n")
            if profile.budget_min and profile.budget_max:
                body_parts.append(f"- Zakres: {profile.budget_min:,} - {profile.budget_max:,} PLN\n")
            elif profile.budget_max:
                body_parts.append(f"- Maksymalnie: {profile.budget_max:,} PLN\n")

        if profile.size_m2_min or profile.size_m2_max:
            body_parts.append(f"\n## Rozmiar działki\n")
            if profile.size_m2_min and profile.size_m2_max:
                body_parts.append(f"- Zakres: {profile.size_m2_min} - {profile.size_m2_max} m²\n")

        body_parts.append(f"\n## Priorytety\n")
        body_parts.append(f"- Cisza: {profile.priority_quietness:.0%}\n")
        body_parts.append(f"- Natura: {profile.priority_nature:.0%}\n")
        body_parts.append(f"- Dostępność: {profile.priority_accessibility:.0%}\n")
        if profile.priority_schools:
            body_parts.append(f"- Szkoły: ważne (ma dzieci)\n")

        body = "".join(body_parts)

        return f"---\n{yaml_content}---\n\n{body}"

    def _markdown_to_profile(self, content: str) -> BuyerProfile:
        """Parse markdown with YAML frontmatter to BuyerProfile."""
        # Extract YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                yaml_content = parts[1].strip()
                data = yaml.safe_load(yaml_content) or {}

                # Flatten nested structures
                profile_data = {
                    "name": data.get("name"),
                    "contact_email": data.get("contact_email"),
                    "contact_phone": data.get("contact_phone"),
                }

                if budget := data.get("budget"):
                    profile_data["budget_min"] = budget.get("min")
                    profile_data["budget_max"] = budget.get("max")
                    profile_data["budget_confidence"] = budget.get("confidence", 0.0)

                if size := data.get("size_m2"):
                    profile_data["size_m2_min"] = size.get("min")
                    profile_data["size_m2_max"] = size.get("max")
                    profile_data["preferred_size_category"] = size.get("category")

                if location := data.get("location"):
                    profile_data["preferred_cities"] = location.get("cities", [])
                    profile_data["preferred_districts"] = location.get("districts", [])
                    profile_data["avoided_districts"] = location.get("avoided", [])

                if priorities := data.get("priorities"):
                    profile_data["priority_quietness"] = priorities.get("quietness", 0.5)
                    profile_data["priority_nature"] = priorities.get("nature", 0.3)
                    profile_data["priority_accessibility"] = priorities.get("accessibility", 0.2)
                    profile_data["priority_schools"] = priorities.get("schools", False)
                    profile_data["priority_transport"] = priorities.get("transport", False)
                    profile_data["priority_shops"] = priorities.get("shops", False)

                profile_data["purpose"] = data.get("purpose")
                profile_data["building_plans"] = data.get("building_plans")
                profile_data["urgency"] = data.get("urgency")
                profile_data["purchase_horizon"] = data.get("purchase_horizon")

                # Remove None values
                profile_data = {k: v for k, v in profile_data.items() if v is not None}

                return BuyerProfile.model_validate(profile_data)

        # No frontmatter - return empty profile
        return BuyerProfile()

    # =========================================================================
    # SESSION ARCHIVES
    # =========================================================================

    def save_session(self, session_id: str, messages: List[Dict[str, Any]]) -> Path:
        """Archive a session transcript as JSONL."""
        self.ensure_exists()

        today = date.today().isoformat()
        filename = f"{today}_{session_id[:8]}.jsonl"
        filepath = self.sessions_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for msg in messages:
                msg["_timestamp"] = datetime.utcnow().isoformat()
                f.write(json.dumps(msg, ensure_ascii=False, default=str) + "\n")

        logger.debug(f"Saved session {session_id} to {filepath}")
        return filepath

    def load_session(self, filename: str) -> List[Dict[str, Any]]:
        """Load a session transcript from JSONL."""
        filepath = self.sessions_dir / filename
        if not filepath.exists():
            return []

        messages = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))

        return messages

    def list_sessions(self, limit: int = 10) -> List[str]:
        """List recent session files (newest first)."""
        if not self.sessions_dir.exists():
            return []

        files = sorted(
            self.sessions_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return [f.name for f in files[:limit]]

    # =========================================================================
    # MEMORY EXTRACTS (Daily memory files)
    # =========================================================================

    def append_memory_extract(self, facts: List[str], session_id: str) -> None:
        """Append extracted facts to today's memory file."""
        self.ensure_exists()

        today = date.today().isoformat()
        filepath = self.memory_dir / f"{today}.md"

        timestamp = datetime.utcnow().strftime("%H:%M:%S")

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"\n## Session {session_id[:8]} ({timestamp})\n\n")
            for fact in facts:
                f.write(f"- {fact}\n")
            f.write("\n")

        logger.debug(f"Appended {len(facts)} facts to {filepath}")

    def get_recent_memory(self, days: int = 7) -> List[str]:
        """Get facts from recent memory files."""
        facts = []

        if not self.memory_dir.exists():
            return facts

        # Get files from last N days
        from datetime import timedelta
        today = date.today()

        for i in range(days):
            day = today - timedelta(days=i)
            filepath = self.memory_dir / f"{day.isoformat()}.md"

            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                # Extract facts (lines starting with "- ")
                for line in content.split("\n"):
                    if line.startswith("- "):
                        facts.append(line[2:].strip())

        return facts

    # =========================================================================
    # PATTERNS (Search patterns over time)
    # =========================================================================

    @property
    def patterns_path(self) -> Path:
        return self.memory_dir / "patterns.json"

    def save_search_pattern(self, criteria: Dict[str, Any]) -> None:
        """Save a search pattern for learning."""
        self.ensure_exists()

        patterns = self._load_patterns()
        patterns.append({
            "timestamp": datetime.utcnow().isoformat(),
            "criteria": criteria,
        })

        # Keep last 100 patterns
        patterns = patterns[-100:]

        with open(self.patterns_path, "w", encoding="utf-8") as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2, default=str)

    def _load_patterns(self) -> List[Dict[str, Any]]:
        """Load saved patterns."""
        if not self.patterns_path.exists():
            return []

        try:
            with open(self.patterns_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def get_frequent_locations(self, min_count: int = 2) -> List[str]:
        """Get frequently searched locations."""
        patterns = self._load_patterns()

        location_counts: Dict[str, int] = {}
        for p in patterns:
            criteria = p.get("criteria", {})
            for key in ["gmina", "miejscowosc", "dzielnica"]:
                if loc := criteria.get(key):
                    location_counts[loc] = location_counts.get(loc, 0) + 1

        return [loc for loc, count in location_counts.items() if count >= min_count]


class WorkspaceManager:
    """Global workspace manager for all users.

    Factory for UserWorkspace instances with shared configuration.
    """

    def __init__(self, config: Optional[WorkspaceConfig] = None):
        self.config = config or WorkspaceConfig()
        self.root = Path(self.config.root_path)

        if self.config.create_if_missing:
            self.root.mkdir(parents=True, exist_ok=True)

    def get_user_workspace(self, user_id: str) -> UserWorkspace:
        """Get workspace for a specific user."""
        return UserWorkspace(user_id, str(self.root))

    def list_users(self) -> List[str]:
        """List all users with workspaces."""
        users_dir = self.root / "users"
        if not users_dir.exists():
            return []

        return [d.name for d in users_dir.iterdir() if d.is_dir()]

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """Remove session files older than N days."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0

        for user_id in self.list_users():
            workspace = self.get_user_workspace(user_id)
            if not workspace.sessions_dir.exists():
                continue

            for session_file in workspace.sessions_dir.glob("*.jsonl"):
                if datetime.fromtimestamp(session_file.stat().st_mtime) < cutoff:
                    session_file.unlink()
                    removed += 1

        logger.info(f"Cleaned up {removed} old session files")
        return removed


# Singleton instance
_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """Get the global workspace manager instance."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager
