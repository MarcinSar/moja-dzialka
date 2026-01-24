"""
Skills Registry - Declarative skill definitions.

Skills are the procedural memory of the agent - they define
what the agent can DO and how to do it.

Each skill has:
- A name and description
- An output schema (Pydantic model)
- A Jinja2 template for the prompt
- An executor that may call tools
"""

from typing import Dict, Type

from ._base import Skill, SkillContext, SkillResult
from .discovery import DiscoverySkill
from .search import SearchSkill
from .evaluation import EvaluationSkill
from .market_analysis import MarketAnalysisSkill
from .lead_capture import LeadCaptureSkill

# Skills registry - maps skill name to skill class
SKILLS_REGISTRY: Dict[str, Type[Skill]] = {
    "discovery": DiscoverySkill,
    "search": SearchSkill,
    "evaluation": EvaluationSkill,
    "market_analysis": MarketAnalysisSkill,
    "lead_capture": LeadCaptureSkill,
}


def get_skill(name: str) -> Skill:
    """Get a skill instance by name."""
    skill_class = SKILLS_REGISTRY.get(name)
    if skill_class is None:
        raise KeyError(f"Unknown skill: {name}. Available: {list(SKILLS_REGISTRY.keys())}")
    return skill_class()


def list_skills() -> Dict[str, str]:
    """List all available skills with descriptions."""
    return {
        name: skill_class().description
        for name, skill_class in SKILLS_REGISTRY.items()
    }


__all__ = [
    # Registry
    "SKILLS_REGISTRY",
    "get_skill",
    "list_skills",
    # Base classes
    "Skill",
    "SkillContext",
    "SkillResult",
    # Skills
    "DiscoverySkill",
    "SearchSkill",
    "EvaluationSkill",
    "MarketAnalysisSkill",
    "LeadCaptureSkill",
]
