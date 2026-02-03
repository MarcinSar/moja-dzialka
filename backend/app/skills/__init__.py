"""
Skills Registry v3 - Declarative skill definitions.

Skills are the procedural memory of the agent - they define
what the agent can DO and how to do it.

v3 Architecture:
- Skills defined in SKILL.md files (YAML frontmatter + instructions)
- SkillLoader parses definitions at runtime
- GateEvaluator validates skill activation
- No more Python skill classes - everything is declarative
"""

from typing import Dict, List, Optional

from ._base import Skill, SkillContext, SkillResult
from .loader import (
    SkillLoader,
    SkillDefinition,
    SkillGates,
    SkillTools,
    SkillTransitions,
    GateEvaluator,
    get_skill_loader,
)


def get_skill(name: str) -> SkillDefinition:
    """Get a skill definition by name.

    v3: Returns SkillDefinition loaded from SKILL.md file.
    """
    loader = get_skill_loader()
    skill = loader.get_skill(name)
    if skill is None:
        available = loader.list_skills()
        raise KeyError(f"Unknown skill: {name}. Available: {available}")
    return skill


def list_skills() -> Dict[str, str]:
    """List all available skills with descriptions."""
    loader = get_skill_loader()
    result = {}
    for name in loader.list_skills():
        skill = loader.get_skill(name)
        if skill:
            result[name] = skill.description
    return result


def get_skill_for_phase(phase: str) -> Optional[SkillDefinition]:
    """Get the primary skill for a given funnel phase.

    Maps funnel phases to their primary skills:
    - DISCOVERY -> discovery
    - SEARCH -> search
    - EVALUATION -> evaluation
    - NEGOTIATION -> market_analysis
    - LEAD_CAPTURE -> lead_capture
    """
    phase_skill_map = {
        "DISCOVERY": "discovery",
        "SEARCH": "search",
        "EVALUATION": "evaluation",
        "NEGOTIATION": "market_analysis",
        "LEAD_CAPTURE": "lead_capture",
    }
    skill_name = phase_skill_map.get(phase)
    if skill_name:
        try:
            return get_skill(skill_name)
        except KeyError:
            return None
    return None


def get_available_skills_for_state(state) -> List[SkillDefinition]:
    """Get skills available given the current agent state.

    Uses GateEvaluator to check which skills can be activated.
    """
    loader = get_skill_loader()
    available = []

    for name in loader.list_skills():  # Returns List[str]
        skill = loader.get_skill(name)
        if skill:
            passed, _ = GateEvaluator.evaluate_gates(skill.gates, state)
            if passed:
                available.append(skill)

    return available


__all__ = [
    # v3 Functions
    "get_skill",
    "list_skills",
    "get_skill_for_phase",
    "get_available_skills_for_state",
    # Base classes
    "Skill",
    "SkillContext",
    "SkillResult",
    # Skill Loader (v3)
    "SkillLoader",
    "SkillDefinition",
    "SkillGates",
    "SkillTools",
    "SkillTransitions",
    "GateEvaluator",
    "get_skill_loader",
]
