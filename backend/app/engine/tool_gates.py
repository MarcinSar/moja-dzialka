"""
Tool Gates - Middleware for tool execution prerequisites.

Gates prevent tools from running when prerequisites aren't met.
Agent receives error as tool_result and self-corrects.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

from loguru import logger

from app.engine.notepad import Notepad


@dataclass
class Gate:
    """A single prerequisite check for a tool."""
    check: str  # Dot-path expression to check
    error: str  # Error message for agent
    hint: Optional[str] = None  # Suggestion for agent


# Gate definitions: tool_name -> list of gates
TOOL_GATES: Dict[str, List[Gate]] = {
    "search_execute": [
        Gate(
            check="notepad.location.validated",
            error="Lokalizacja nie jest zwalidowana.",
            hint="Najpierw użyj location_search i location_confirm aby zwalidować lokalizację.",
        ),
    ],
    "search_refine": [
        Gate(
            check="notepad.search_results is not None",
            error="Brak wyników wyszukiwania do doprecyzowania.",
            hint="Najpierw wykonaj search_execute.",
        ),
    ],
    "search_similar": [
        Gate(
            check="notepad.search_results is not None",
            error="Brak wyników wyszukiwania.",
            hint="Najpierw wykonaj search_execute aby mieć bazę do porównania.",
        ),
    ],
    "search_adjacent": [
        Gate(
            check="notepad.search_results is not None",
            error="Brak wyników wyszukiwania.",
            hint="Najpierw znajdź działkę, potem szukaj sąsiednich.",
        ),
    ],
    "results_load_page": [
        Gate(
            check="notepad.search_results is not None",
            error="Brak wyników wyszukiwania do paginacji.",
            hint="Najpierw wykonaj search_execute.",
        ),
    ],
    "parcel_compare": [
        Gate(
            check="notepad.search_results is not None",
            error="Brak wyników wyszukiwania do porównania.",
            hint="Najpierw znajdź działki przez search_execute.",
        ),
    ],
    "lead_capture": [
        Gate(
            check="has_contact_data",
            error="Brak danych kontaktowych.",
            hint="Poproś użytkownika o email lub telefon.",
        ),
    ],
}


def _evaluate_check(check: str, notepad: Notepad, tool_params: Dict[str, Any]) -> bool:
    """Evaluate a gate check expression against notepad state.

    Supports:
    - notepad.location.validated -> notepad.location and notepad.location.validated
    - notepad.search_results is not None -> notepad.search_results is not None
    - has_contact_data -> special check for lead_capture params
    """
    if check == "has_contact_data":
        return bool(tool_params.get("email") or tool_params.get("phone"))

    if "notepad." in check:
        parts = check.replace("notepad.", "").split(".")

        obj = notepad
        for part in parts:
            # Handle "is not None" at end
            if part == "is not None":
                return obj is not None
            if obj is None:
                return False
            obj = getattr(obj, part, None)

        # If we get here without "is not None", treat as truthy check
        return bool(obj)

    return True  # Unknown check passes by default


def check_gates(tool_name: str, notepad: Notepad, tool_params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """Check all gates for a tool.

    Args:
        tool_name: Name of the tool being called
        notepad: Current session notepad
        tool_params: Parameters passed to the tool

    Returns:
        None if all gates pass, or error dict for agent
    """
    gates = TOOL_GATES.get(tool_name)
    if not gates:
        return None  # No gates = always allowed

    if tool_params is None:
        tool_params = {}

    for gate in gates:
        if not _evaluate_check(gate.check, notepad, tool_params):
            logger.info(f"Gate blocked {tool_name}: {gate.error}")
            result = {
                "error": gate.error,
                "gate_blocked": True,
                "tool": tool_name,
            }
            if gate.hint:
                result["hint"] = gate.hint
            return result

    return None  # All gates passed
