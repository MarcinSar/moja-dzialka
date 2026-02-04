"""
Skill Loader - Progressive skill loading with SKILL.md support.

Implements OpenClaw-style skill definitions using YAML frontmatter in markdown files.
Each skill has:
- Gates: conditions for when the skill can be used
- Tools: which tools are available to the skill
- Transitions: what happens after skill completion

SKILL.md Format:
```markdown
---
name: discovery
description: Zbieranie preferencji użytkownika
version: "1.0"

gates:
  requires: []
  requires_any: []
  blocks: [search]

tools:
  always_available:
    - resolve_location
    - get_available_locations
  context_available:
    - propose_search_preferences
  restricted: []

transitions:
  on_success: search
  on_user_request:
    - search
    - evaluation

model:
  default: haiku
  upgrade_on_complexity: true
---

# Discovery Skill

Detailed skill instructions in markdown...
```
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

import yaml
from loguru import logger
from pydantic import BaseModel, Field

from app.memory import AgentState, FunnelPhase


# =============================================================================
# SKILL.MD SCHEMA
# =============================================================================

class SkillGates(BaseModel):
    """Gates define when a skill can be activated."""

    requires: List[str] = Field(
        default_factory=list,
        description="All conditions must be true"
    )
    requires_any: List[str] = Field(
        default_factory=list,
        description="At least one condition must be true"
    )
    blocks: List[str] = Field(
        default_factory=list,
        description="Skills that cannot run while this is active"
    )


class SkillTools(BaseModel):
    """Tool access configuration for a skill."""

    always_available: List[str] = Field(
        default_factory=list,
        description="Tools always available to this skill"
    )
    context_available: List[str] = Field(
        default_factory=list,
        description="Tools available based on context"
    )
    restricted: List[str] = Field(
        default_factory=list,
        description="Tools explicitly blocked for this skill"
    )


class SkillTransitions(BaseModel):
    """Transition rules after skill completion."""

    on_success: Optional[str] = Field(
        None,
        description="Default next skill on success"
    )
    on_failure: Optional[str] = Field(
        None,
        description="Skill to try on failure"
    )
    on_user_request: List[str] = Field(
        default_factory=list,
        description="Skills user can explicitly request"
    )


class SkillModelConfig(BaseModel):
    """Model configuration for the skill."""

    default: str = Field(
        default="haiku",
        description="Default model (haiku, sonnet)"
    )
    upgrade_on_complexity: bool = Field(
        default=False,
        description="Upgrade to better model for complex tasks"
    )


class SkillDefinition(BaseModel):
    """Complete skill definition from SKILL.md."""

    name: str
    description: str
    version: str = "1.0"

    gates: SkillGates = Field(default_factory=SkillGates)
    tools: SkillTools = Field(default_factory=SkillTools)
    transitions: SkillTransitions = Field(default_factory=SkillTransitions)
    model: SkillModelConfig = Field(default_factory=SkillModelConfig)

    # Markdown body (instructions)
    instructions: str = ""


# =============================================================================
# GATE EVALUATION
# =============================================================================

class GateEvaluator:
    """Evaluate skill gates against agent state."""

    # Gate condition → evaluation function
    CONDITIONS = {
        # Phase conditions
        "phase:discovery": lambda s: s.working.current_phase == FunnelPhase.DISCOVERY,
        "phase:search": lambda s: s.working.current_phase == FunnelPhase.SEARCH,
        "phase:evaluation": lambda s: s.working.current_phase == FunnelPhase.EVALUATION,
        "phase:lead_capture": lambda s: s.working.current_phase == FunnelPhase.LEAD_CAPTURE,
        "phase:negotiation": lambda s: s.working.current_phase == FunnelPhase.NEGOTIATION,
        "phase:retention": lambda s: s.working.current_phase == FunnelPhase.RETENTION,

        # Search state conditions
        "has:preferences_proposed": lambda s: s.working.search_state.preferences_proposed,
        "has:preferences_approved": lambda s: s.working.search_state.preferences_approved,
        "has:search_results": lambda s: len(s.working.search_state.current_results) > 0,
        "has:favorites": lambda s: len(s.working.search_state.favorited_parcels) > 0,

        # Profile conditions
        "has:location": lambda s: s.workflow.funnel_progress.location_collected,
        "has:budget": lambda s: s.workflow.funnel_progress.budget_collected,
        "has:contact": lambda s: s.workflow.funnel_progress.contact_captured,

        # Session conditions
        "is:returning_user": lambda s: s.semantic.total_sessions > 1,
        "is:engaged": lambda s: s.semantic.engagement_score > 0.5,
    }

    @classmethod
    def evaluate_condition(cls, condition: str, state: AgentState) -> bool:
        """Evaluate a single gate condition."""
        evaluator = cls.CONDITIONS.get(condition)
        if evaluator is None:
            logger.warning(f"Unknown gate condition: {condition}")
            return True  # Unknown conditions pass by default

        try:
            return evaluator(state)
        except Exception as e:
            logger.error(f"Error evaluating gate {condition}: {e}")
            return False

    @classmethod
    def evaluate_gates(cls, gates: SkillGates, state: AgentState) -> tuple[bool, Optional[str]]:
        """Evaluate all gates for a skill.

        Returns:
            Tuple of (passed, reason_if_failed)
        """
        # Check all required conditions
        for condition in gates.requires:
            if not cls.evaluate_condition(condition, state):
                return False, f"Required condition not met: {condition}"

        # Check at least one of requires_any
        if gates.requires_any:
            if not any(cls.evaluate_condition(c, state) for c in gates.requires_any):
                return False, f"None of the conditions met: {gates.requires_any}"

        return True, None


# =============================================================================
# SKILL LOADER
# =============================================================================

class SkillLoader:
    """Load and manage skill definitions from SKILL.md files.

    Supports:
    - Loading from markdown files with YAML frontmatter
    - Progressive disclosure (context-aware tool availability)
    - Gate validation before skill activation
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        """Initialize skill loader.

        Args:
            skills_dir: Directory containing SKILL.md files
        """
        if skills_dir is None:
            skills_dir = Path(__file__).parent / "definitions"

        self.skills_dir = skills_dir
        self._cache: Dict[str, SkillDefinition] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Ensure skills are loaded from files."""
        if self._loaded:
            return

        self._load_all_skills()
        self._loaded = True

    def _load_all_skills(self) -> None:
        """Load all SKILL.md files from the skills directory."""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return

        for filepath in self.skills_dir.glob("*.md"):
            try:
                skill = self._parse_skill_file(filepath)
                self._cache[skill.name] = skill
                logger.debug(f"Loaded skill: {skill.name} from {filepath.name}")
            except Exception as e:
                logger.error(f"Failed to load skill from {filepath}: {e}")

    def _parse_skill_file(self, filepath: Path) -> SkillDefinition:
        """Parse a SKILL.md file."""
        content = filepath.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        if not content.startswith("---"):
            raise ValueError(f"No YAML frontmatter in {filepath}")

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid frontmatter format in {filepath}")

        yaml_content = parts[1].strip()
        markdown_body = parts[2].strip()

        # Parse YAML
        data = yaml.safe_load(yaml_content)

        # Build skill definition
        return SkillDefinition(
            name=data.get("name", filepath.stem),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            gates=SkillGates(**data.get("gates", {})),
            tools=SkillTools(**data.get("tools", {})),
            transitions=SkillTransitions(**data.get("transitions", {})),
            model=SkillModelConfig(**data.get("model", {})),
            instructions=markdown_body,
        )

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        """Get a skill definition by name."""
        self._ensure_loaded()
        return self._cache.get(name)

    def list_skills(self) -> List[str]:
        """List all available skill names."""
        self._ensure_loaded()
        return list(self._cache.keys())

    def get_available_skills(self, state: AgentState) -> List[str]:
        """Get skills that can be activated in the current state.

        Args:
            state: Current agent state

        Returns:
            List of skill names that pass gate validation
        """
        self._ensure_loaded()
        available = []

        for name, skill in self._cache.items():
            passed, _ = GateEvaluator.evaluate_gates(skill.gates, state)
            if passed:
                available.append(name)

        return available

    def validate_skill(self, name: str, state: AgentState) -> tuple[bool, Optional[str]]:
        """Validate if a skill can be activated.

        Args:
            name: Skill name
            state: Current agent state

        Returns:
            Tuple of (can_activate, reason_if_not)
        """
        skill = self.get_skill(name)
        if skill is None:
            return False, f"Unknown skill: {name}"

        return GateEvaluator.evaluate_gates(skill.gates, state)

    def get_tools_for_skill(
        self,
        name: str,
        state: AgentState,
    ) -> List[str]:
        """Get tools available to a skill based on context.

        Args:
            name: Skill name
            state: Current agent state

        Returns:
            List of tool names
        """
        skill = self.get_skill(name)
        if skill is None:
            return []

        tools = set(skill.tools.always_available)

        # Add context-dependent tools based on state
        for tool_name in skill.tools.context_available:
            # Check if tool is appropriate for current context
            # This is simplified - could be more sophisticated
            if self._is_tool_contextually_available(tool_name, state):
                tools.add(tool_name)

        # Remove restricted tools
        tools -= set(skill.tools.restricted)

        return list(tools)

    def _is_tool_contextually_available(
        self,
        tool_name: str,
        state: AgentState,
    ) -> bool:
        """Check if a tool is available based on context."""
        # Propose preferences available only if not already approved
        if tool_name == "propose_search_preferences":
            return not state.working.search_state.preferences_approved

        # Approve preferences available only if proposed
        if tool_name == "approve_search_preferences":
            return state.working.search_state.preferences_proposed

        # Execute search available only if approved
        if tool_name == "execute_search":
            return state.working.search_state.preferences_approved

        # Parcel details available only if search returned results
        if tool_name in ("get_parcel_full_context", "get_parcel_neighborhood"):
            return len(state.working.search_state.current_results) > 0

        # Default: available
        return True

    def get_next_skill(
        self,
        current_skill: str,
        state: AgentState,
        success: bool = True,
    ) -> Optional[str]:
        """Get the next skill based on transitions.

        Args:
            current_skill: Name of the current skill
            state: Current agent state
            success: Whether current skill succeeded

        Returns:
            Name of next skill, or None if no transition defined
        """
        skill = self.get_skill(current_skill)
        if skill is None:
            return None

        transitions = skill.transitions

        if success and transitions.on_success:
            # Validate next skill can be activated
            can_activate, _ = self.validate_skill(transitions.on_success, state)
            if can_activate:
                return transitions.on_success

        if not success and transitions.on_failure:
            can_activate, _ = self.validate_skill(transitions.on_failure, state)
            if can_activate:
                return transitions.on_failure

        return None

    def get_model_for_skill(
        self,
        name: str,
        is_complex: bool = False,
    ) -> str:
        """Get the model to use for a skill.

        Args:
            name: Skill name
            is_complex: Whether the task is complex

        Returns:
            Model identifier (e.g., "claude-haiku-4-5")
        """
        skill = self.get_skill(name)
        if skill is None:
            return "claude-haiku-4-5"

        model_config = skill.model

        if is_complex and model_config.upgrade_on_complexity:
            return "claude-sonnet-4-20250514"

        model_map = {
            "haiku": "claude-haiku-4-5",
            "sonnet": "claude-sonnet-4-20250514",
            "opus": "claude-opus-4-20250514",
        }

        return model_map.get(model_config.default, "claude-haiku-4-5")


# =============================================================================
# SINGLETON
# =============================================================================

_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """Get the global skill loader instance."""
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader
