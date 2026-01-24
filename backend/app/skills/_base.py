"""
Base Skill Class - Foundation for all skills.

Skills are declarative definitions of agent capabilities.
They define the output schema and prompt template.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Type, Optional, Dict, Any, List, Union

from pydantic import BaseModel, Field
from jinja2 import Template, Environment, FileSystemLoader


class SkillContext(BaseModel):
    """Context passed to skill for prompt rendering.

    Memory layers can be either Pydantic models or dicts to allow
    templates to call methods on them (e.g., workflow.funnel_progress.is_ready_for_search()).
    """
    # Memory layers - accept Any to allow both dicts and Pydantic models
    core: Any = Field(default_factory=dict)
    working: Any = Field(default_factory=dict)
    semantic: Any = Field(default_factory=dict)
    episodic: Any = Field(default_factory=dict)
    workflow: Any = Field(default_factory=dict)
    preferences: Any = Field(default_factory=dict)

    # Current interaction
    user_message: str = ""
    skill_name: str = ""

    # Additional context
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class SkillResult(BaseModel):
    """Base result from skill execution."""
    thinking: str = Field(
        default="",
        description="Internal reasoning (not shown to user)"
    )
    ai_response: str = Field(
        default="",
        description="Response to show to user"
    )
    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tool calls to execute"
    )

    # State updates
    state_updates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Updates to apply to agent state"
    )


class Skill(ABC):
    """Base class for all skills (procedural memory).

    Each skill defines:
    - What it does (description)
    - What it outputs (output_model)
    - How to prompt (template)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this skill does."""
        pass

    @property
    @abstractmethod
    def output_model(self) -> Type[BaseModel]:
        """Pydantic model for structured output."""
        pass

    @property
    def template_name(self) -> str:
        """Template filename (default: {name}.j2)."""
        return f"{self.name}.j2"

    @property
    def template_dir(self) -> Path:
        """Directory containing skill templates."""
        return Path(__file__).parent / "templates"

    def get_template(self) -> Template:
        """Load Jinja2 template for this skill.

        Uses the shared template environment with custom filters.
        """
        from app.memory.templates import get_template_env

        # Get the shared environment and add skill template directory
        env = get_template_env()
        # Add the skill templates directory to the loader
        env.loader.searchpath.append(str(self.template_dir))

        return env.get_template(self.template_name)

    def prepare_prompt(self, context: SkillContext) -> str:
        """Render prompt with context."""
        template = self.get_template()
        return template.render(**context.model_dump())

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get tools available to this skill.

        Override in subclasses to restrict available tools.
        Default: all tools are available.
        """
        return []  # Will be filled by executor with relevant tools

    def validate_context(self, context: SkillContext) -> Optional[str]:
        """Validate context before execution.

        Returns error message if invalid, None if valid.
        """
        return None

    def post_process(self, result: BaseModel, context: SkillContext) -> BaseModel:
        """Post-process the skill result.

        Override to add custom logic after LLM response.
        """
        return result

    def __repr__(self) -> str:
        return f"<Skill: {self.name}>"


class ToolCallingSkill(Skill):
    """Skill that uses tool calling.

    These skills allow the LLM to call tools during execution.
    """

    @property
    @abstractmethod
    def available_tools(self) -> List[str]:
        """List of tool names this skill can use."""
        pass

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for this skill."""
        # Import here to avoid circular imports
        from app.engine.tools_registry import AGENT_TOOLS

        return [
            tool for tool in AGENT_TOOLS
            if tool["name"] in self.available_tools
        ]
