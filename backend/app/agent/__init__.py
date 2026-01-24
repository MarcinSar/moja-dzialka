"""
AI Agent module for conversational parcel search.

Provides tools definitions and execution for the PropertyAdvisorAgent.
Uses Claude API with tool calling for natural language interaction.

Note: The main agent logic is now in app.engine.property_advisor_agent
and app.engine.agent_coordinator (v2 architecture).

Tool definitions are in app.engine.tools_registry.
Tool execution is in app.engine.tool_executor.
This module provides backwards compatibility imports.
"""

# Backwards compatibility: Import from new locations
from app.engine.tools_registry import AGENT_TOOLS
from app.engine.tool_executor import execute_tool, ToolExecutor
from app.engine.price_data import DISTRICT_PRICES, SEGMENT_DESCRIPTIONS

__all__ = [
    "AGENT_TOOLS",
    "execute_tool",
    "ToolExecutor",
    "DISTRICT_PRICES",
    "SEGMENT_DESCRIPTIONS",
]
