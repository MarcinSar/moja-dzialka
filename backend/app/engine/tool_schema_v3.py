"""
Tool Schema V3 - Enhanced tool definitions with metadata.

V3 adds to the standard Claude tool schema:
- Reliability score (how often does this tool work)
- Cost indicator (computational/monetary cost)
- Examples with expected output
- Composition hints (what tools to use before/after)
- Natural language triggers
- Policy tags (freemium, phase-based)

This enables:
1. Better tool selection by the agent
2. Policy enforcement (freemium, rate limits)
3. Tool composition patterns
4. Better error handling
"""

from typing import Dict, Any, List, Optional, Set
from enum import Enum
from pydantic import BaseModel, Field


class ReliabilityScore(str, Enum):
    """How reliable is this tool?"""
    HIGH = "high"       # >95% success rate
    MEDIUM = "medium"   # 80-95% success rate
    LOW = "low"         # <80% success rate


class CostIndicator(str, Enum):
    """Cost indicator for tool execution."""
    FREE = "free"           # No cost, instant
    CHEAP = "cheap"         # Minimal cost (<10ms, local)
    MODERATE = "moderate"   # Moderate cost (<100ms, DB query)
    EXPENSIVE = "expensive" # High cost (<1s, complex query)
    PREMIUM = "premium"     # Premium feature (requires payment)


class PolicyTag(str, Enum):
    """Policy tags for tool access control."""
    FREE_TIER = "free_tier"         # Available to all users
    PAID_TIER = "paid_tier"         # Requires payment
    RATE_LIMITED = "rate_limited"   # Subject to rate limits
    PHASE_DISCOVERY = "phase_discovery"   # Only in DISCOVERY phase
    PHASE_SEARCH = "phase_search"         # Only in SEARCH phase
    PHASE_EVALUATION = "phase_evaluation" # Only in EVALUATION phase
    PHASE_LEAD = "phase_lead"             # Only in LEAD_CAPTURE phase


class ToolExample(BaseModel):
    """Example of tool usage with expected output."""
    description: str = Field(..., description="What this example demonstrates")
    input: Dict[str, Any] = Field(..., description="Example input parameters")
    output_preview: str = Field(..., description="Expected output (truncated)")
    notes: Optional[str] = Field(None, description="Additional notes")


class CompositionHint(BaseModel):
    """Hints for tool composition."""
    before: List[str] = Field(
        default_factory=list,
        description="Tools that should typically run before this one"
    )
    after: List[str] = Field(
        default_factory=list,
        description="Tools that typically run after this one"
    )
    combines_with: List[str] = Field(
        default_factory=list,
        description="Tools that work well in combination"
    )
    conflicts_with: List[str] = Field(
        default_factory=list,
        description="Tools that should not be used together"
    )


class ToolDefinitionV3(BaseModel):
    """Enhanced tool definition with V3 metadata.

    This extends the standard Claude tool schema with additional
    metadata for better tool selection and policy enforcement.
    """

    # Standard Claude tool schema fields
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Tool description (shown to LLM)")
    input_schema: Dict[str, Any] = Field(..., description="JSON schema for inputs")

    # V3 Enhanced fields
    reliability: ReliabilityScore = Field(
        default=ReliabilityScore.HIGH,
        description="How reliable is this tool"
    )
    cost: CostIndicator = Field(
        default=CostIndicator.MODERATE,
        description="Cost indicator"
    )
    policies: List[PolicyTag] = Field(
        default_factory=lambda: [PolicyTag.FREE_TIER],
        description="Policy tags for access control"
    )

    # Usage guidance
    when_to_use: str = Field(
        default="",
        description="Detailed guidance on when to use this tool"
    )
    when_not_to_use: str = Field(
        default="",
        description="When to avoid using this tool"
    )
    natural_triggers: List[str] = Field(
        default_factory=list,
        description="Natural language phrases that trigger this tool"
    )

    # Examples
    examples: List[ToolExample] = Field(
        default_factory=list,
        description="Usage examples"
    )

    # Composition
    composition: CompositionHint = Field(
        default_factory=CompositionHint,
        description="Tool composition hints"
    )

    # Metadata
    category: str = Field(default="general", description="Tool category")
    version: str = Field(default="1.0", description="Tool version")

    def to_claude_schema(self) -> Dict[str, Any]:
        """Convert to standard Claude tool schema."""
        return {
            "name": self.name,
            "description": self._build_enhanced_description(),
            "input_schema": self.input_schema,
        }

    def _build_enhanced_description(self) -> str:
        """Build enhanced description with V3 metadata."""
        parts = [self.description]

        if self.when_to_use:
            parts.append(f"\n\nKIEDY UŻYWAĆ: {self.when_to_use}")

        if self.when_not_to_use:
            parts.append(f"\nKIEDY NIE UŻYWAĆ: {self.when_not_to_use}")

        if self.reliability == ReliabilityScore.LOW:
            parts.append(f"\n⚠️ UWAGA: Niska niezawodność - sprawdź wyniki")

        if self.cost == CostIndicator.EXPENSIVE:
            parts.append(f"\n⏱️ UWAGA: Wolne zapytanie - używaj oszczędnie")

        if self.composition.before:
            parts.append(f"\n📋 NAJPIERW: {', '.join(self.composition.before)}")

        return "".join(parts)

    class Config:
        use_enum_values = True


# =============================================================================
# TOOL REGISTRY V3
# =============================================================================

class ToolRegistryV3:
    """Registry for V3 tool definitions with policy enforcement."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinitionV3] = {}
        self._by_category: Dict[str, List[str]] = {}

    def register(self, tool: ToolDefinitionV3) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool

        # Index by category
        if tool.category not in self._by_category:
            self._by_category[tool.category] = []
        if tool.name not in self._by_category[tool.category]:
            self._by_category[tool.category].append(tool.name)

    def get(self, name: str) -> Optional[ToolDefinitionV3]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_claude_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get Claude-compatible schema for a tool."""
        tool = self._tools.get(name)
        if tool:
            return tool.to_claude_schema()
        return None

    def get_all_claude_schemas(
        self,
        filter_policies: Optional[Set[PolicyTag]] = None,
        filter_category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all tool schemas with optional filtering.

        Args:
            filter_policies: Only include tools with these policies
            filter_category: Only include tools in this category

        Returns:
            List of Claude-compatible tool schemas
        """
        schemas = []

        for tool in self._tools.values():
            # Filter by category
            if filter_category and tool.category != filter_category:
                continue

            # Filter by policies
            if filter_policies:
                tool_policies = set(tool.policies)
                if not tool_policies.intersection(filter_policies):
                    continue

            schemas.append(tool.to_claude_schema())

        return schemas

    def get_tools_for_agent(
        self,
        agent_type: str,
        user_tier: str = "free",
        current_phase: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get tools available for a specific agent and user tier.

        Args:
            agent_type: Type of agent (discovery, search, analyst, etc.)
            user_tier: User's payment tier (free, paid)
            current_phase: Current funnel phase

        Returns:
            List of Claude-compatible tool schemas
        """
        # Map agent types to categories
        agent_categories = {
            "discovery": ["preference", "location", "general"],
            "search": ["search", "location", "general"],
            "analyst": ["context", "pricing", "comparison", "general"],
            "narrator": ["context", "general"],
            "feedback": ["preference", "search", "general"],
            "lead": ["lead", "general"],
        }

        categories = agent_categories.get(agent_type, ["general"])

        # Build policy filter
        allowed_policies = {PolicyTag.FREE_TIER}
        if user_tier == "paid":
            allowed_policies.add(PolicyTag.PAID_TIER)

        # Add phase-specific policies
        if current_phase:
            phase_policy_map = {
                "DISCOVERY": PolicyTag.PHASE_DISCOVERY,
                "SEARCH": PolicyTag.PHASE_SEARCH,
                "EVALUATION": PolicyTag.PHASE_EVALUATION,
                "LEAD_CAPTURE": PolicyTag.PHASE_LEAD,
            }
            if phase_policy := phase_policy_map.get(current_phase):
                allowed_policies.add(phase_policy)

        # Collect tools
        schemas = []
        for category in categories:
            tool_names = self._by_category.get(category, [])
            for name in tool_names:
                tool = self._tools[name]

                # Check policy
                tool_policies = set(tool.policies)
                if not tool_policies.intersection(allowed_policies):
                    continue

                schemas.append(tool.to_claude_schema())

        return schemas

    def list_categories(self) -> List[str]:
        """List all tool categories."""
        return list(self._by_category.keys())

    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """List tool names, optionally filtered by category."""
        if category:
            return self._by_category.get(category, [])
        return list(self._tools.keys())


# =============================================================================
# TOOL DEFINITIONS - PREFERENCE MANAGEMENT
# =============================================================================

TOOLS_V3_PREFERENCE = [
    ToolDefinitionV3(
        name="propose_search_preferences",
        description="""Zaproponuj preferencje wyszukiwania działki na podstawie wymagań użytkownika.
ZAWSZE używaj tego narzędzia przed execute_search.""",
        input_schema={
            "type": "object",
            "properties": {
                "gmina": {
                    "type": "string",
                    "description": "Gmina (Gdańsk, Gdynia, Sopot)"
                },
                "miejscowosc": {
                    "type": "string",
                    "description": "Miejscowość w ramach gminy"
                },
                "dzielnica": {
                    "type": "string",
                    "description": "Dzielnica (np. Osowa, Kokoszki)"
                },
                "min_area_m2": {
                    "type": "integer",
                    "description": "Minimalna powierzchnia w m²"
                },
                "max_area_m2": {
                    "type": "integer",
                    "description": "Maksymalna powierzchnia w m²"
                },
                "ownership_type": {
                    "type": "string",
                    "enum": ["prywatna", "publiczna", "spółdzielcza", "kościelna", "inna"],
                    "description": "Typ własności (prywatna = można kupić!)"
                },
                "build_status": {
                    "type": "string",
                    "enum": ["zabudowana", "niezabudowana"],
                    "description": "Status zabudowy"
                },
                "size_category": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["mala", "pod_dom", "duza", "bardzo_duza"]},
                    "description": "Kategorie rozmiaru"
                },
                "quietness_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Kategorie ciszy [bardzo_cicha, cicha, umiarkowana, glosna]"
                },
                "nature_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Bliskość natury [bardzo_blisko, blisko, srednio, daleko]"
                },
                "pog_residential": {
                    "type": "boolean",
                    "description": "Tylko strefy mieszkaniowe POG"
                },
                "max_dist_to_school_m": {
                    "type": "integer",
                    "description": "Max odległość do szkoły (m)"
                },
                "max_dist_to_shop_m": {
                    "type": "integer",
                    "description": "Max odległość do sklepu (m)"
                },
                "max_dist_to_bus_stop_m": {
                    "type": "integer",
                    "description": "Max odległość do przystanku (m)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max liczba wyników (default: 20)"
                },
            },
            "required": [],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.FREE,
        policies=[PolicyTag.FREE_TIER, PolicyTag.PHASE_DISCOVERY, PolicyTag.PHASE_SEARCH],
        when_to_use="Gdy użytkownik podaje kryteria wyszukiwania działki",
        when_not_to_use="Gdy preferencje już zostały zaproponowane i zatwierdzone",
        natural_triggers=[
            "szukam działki",
            "chcę znaleźć",
            "interesuje mnie",
            "w okolicach",
            "cicha okolica",
            "blisko lasu",
        ],
        examples=[
            ToolExample(
                description="Cicha działka pod dom w Osowej",
                input={
                    "gmina": "Gdańsk",
                    "dzielnica": "Osowa",
                    "ownership_type": "prywatna",
                    "build_status": "niezabudowana",
                    "size_category": ["pod_dom"],
                    "quietness_categories": ["bardzo_cicha", "cicha"],
                },
                output_preview='{"status": "proposed", "count": 127}',
            ),
        ],
        composition=CompositionHint(
            after=["approve_search_preferences", "count_matching_parcels_quick"],
        ),
        category="preference",
    ),

    ToolDefinitionV3(
        name="approve_search_preferences",
        description="Zatwierdź zaproponowane preferencje wyszukiwania. Użyj po propose_search_preferences.",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.FREE,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Gdy użytkownik akceptuje zaproponowane preferencje",
        natural_triggers=["tak", "szukaj", "dobrze", "ok", "zgoda"],
        composition=CompositionHint(
            before=["propose_search_preferences"],
            after=["execute_search"],
        ),
        category="preference",
    ),

    ToolDefinitionV3(
        name="count_matching_parcels_quick",
        description="Szybkie sprawdzenie ile działek pasuje do kryteriów (checkpoint).",
        input_schema={
            "type": "object",
            "properties": {
                "preferences": {
                    "type": "object",
                    "description": "Preferencje do sprawdzenia"
                },
            },
            "required": [],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.CHEAP,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Przed wyszukiwaniem, żeby sprawdzić czy kryteria nie są zbyt wąskie/szerokie",
        composition=CompositionHint(
            before=["propose_search_preferences"],
            after=["execute_search"],
        ),
        category="preference",
    ),
]


# =============================================================================
# TOOL DEFINITIONS - SEARCH
# =============================================================================

TOOLS_V3_SEARCH = [
    ToolDefinitionV3(
        name="execute_search",
        description="""Wykonaj hybrydowe wyszukiwanie działek (graf + wektor + przestrzenne).
NAJPIERW użyj propose_search_preferences i approve_search_preferences.""",
        input_schema={
            "type": "object",
            "properties": {
                "use_preferences": {
                    "type": "boolean",
                    "description": "Użyj zatwierdzonych preferencji (default: true)"
                },
                "additional_filters": {
                    "type": "object",
                    "description": "Dodatkowe filtry (łączone z preferencjami)"
                },
            },
            "required": [],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.EXPENSIVE,
        policies=[PolicyTag.FREE_TIER, PolicyTag.RATE_LIMITED],
        when_to_use="Po zatwierdzeniu preferencji, gdy użytkownik chce zobaczyć wyniki",
        when_not_to_use="Przed zatwierdzeniem preferencji",
        composition=CompositionHint(
            before=["propose_search_preferences", "approve_search_preferences"],
            after=["get_parcel_full_context", "compare_parcels"],
        ),
        category="search",
    ),

    ToolDefinitionV3(
        name="find_adjacent_parcels",
        description="Znajdź działki sąsiadujące z daną działką (przez ADJACENT_TO).",
        input_schema={
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki (np. 220611_2.0001.1234)"
                },
                "min_shared_border_m": {
                    "type": "number",
                    "description": "Minimalna długość wspólnej granicy (m)"
                },
            },
            "required": ["parcel_id"],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.MODERATE,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Gdy użytkownik pyta o sąsiednie działki lub chce kupić więcej niż jedną",
        natural_triggers=["sąsiednie", "obok", "sąsiaduje", "wspólna granica"],
        category="search",
    ),

    ToolDefinitionV3(
        name="search_near_specific_poi",
        description="Znajdź działki blisko konkretnego POI (szkoły, sklepu) po nazwie.",
        input_schema={
            "type": "object",
            "properties": {
                "poi_type": {
                    "type": "string",
                    "enum": ["school", "shop", "bus_stop", "water", "forest"],
                    "description": "Typ POI"
                },
                "poi_name": {
                    "type": "string",
                    "description": "Nazwa POI (np. 'SP nr 45', 'Biedronka')"
                },
                "max_distance_m": {
                    "type": "integer",
                    "description": "Maksymalna odległość (m)"
                },
            },
            "required": ["poi_type", "poi_name"],
        },
        reliability=ReliabilityScore.MEDIUM,
        cost=CostIndicator.MODERATE,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Gdy użytkownik wymienia konkretne POI po nazwie",
        natural_triggers=["blisko szkoły", "przy szkole", "niedaleko"],
        category="search",
    ),

    ToolDefinitionV3(
        name="find_similar_by_graph",
        description="Znajdź działki podobne strukturalnie (przez graph embeddings).",
        input_schema={
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki wzorcowej"
                },
                "limit": {
                    "type": "integer",
                    "description": "Liczba wyników (default: 10)"
                },
            },
            "required": ["parcel_id"],
        },
        reliability=ReliabilityScore.MEDIUM,
        cost=CostIndicator.EXPENSIVE,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Gdy użytkownik chce znaleźć działki podobne do tej którą lubi",
        natural_triggers=["podobne", "takie same", "analogiczne"],
        category="search",
    ),
]


# =============================================================================
# TOOL DEFINITIONS - CONTEXT & ANALYSIS
# =============================================================================

TOOLS_V3_CONTEXT = [
    ToolDefinitionV3(
        name="get_parcel_full_context",
        description="Pobierz pełne dane działki (68+ cech).",
        input_schema={
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki"
                },
            },
            "required": ["parcel_id"],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.MODERATE,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Gdy użytkownik pyta o szczegóły konkretnej działki",
        natural_triggers=["szczegóły", "więcej informacji", "pokaż działkę"],
        category="context",
    ),

    ToolDefinitionV3(
        name="compare_parcels",
        description="Porównaj 2-5 działek w tabeli.",
        input_schema={
            "type": "object",
            "properties": {
                "parcel_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista ID działek do porównania (2-5)"
                },
            },
            "required": ["parcel_ids"],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.EXPENSIVE,
        policies=[PolicyTag.FREE_TIER, PolicyTag.PHASE_EVALUATION],
        when_to_use="Gdy użytkownik chce porównać kilka działek",
        natural_triggers=["porównaj", "która lepsza", "vs", "versus"],
        category="comparison",
    ),

    ToolDefinitionV3(
        name="get_district_prices",
        description="Pobierz ceny gruntów w dzielnicy.",
        input_schema={
            "type": "object",
            "properties": {
                "district": {
                    "type": "string",
                    "description": "Nazwa dzielnicy"
                },
            },
            "required": ["district"],
        },
        reliability=ReliabilityScore.MEDIUM,
        cost=CostIndicator.CHEAP,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Gdy użytkownik pyta o ceny w okolicy",
        natural_triggers=["ceny", "ile kosztuje", "wartość"],
        category="pricing",
    ),
]


# =============================================================================
# TOOL DEFINITIONS - LOCATION
# =============================================================================

TOOLS_V3_LOCATION = [
    ToolDefinitionV3(
        name="search_locations",
        description="Przeszukaj bazę lokalizacji (dzielnice, gminy, powiaty, województwa).",
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nazwa lokalizacji w mianowniku"
                },
                "level": {
                    "type": "string",
                    "description": "Poziom: dzielnica/gmina/powiat/wojewodztwo"
                },
                "parent_name": {
                    "type": "string",
                    "description": "Nazwa nadrzędnej lokalizacji"
                },
            },
            "required": ["name"],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.CHEAP,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Gdy użytkownik podaje nazwę lokalizacji",
        when_not_to_use="",
        composition=CompositionHint(
            after=["confirm_location"],
        ),
        category="location",
    ),
    ToolDefinitionV3(
        name="confirm_location",
        description="Potwierdź i zapisz lokalizację (po search_locations i potwierdzeniu użytkownika).",
        input_schema={
            "type": "object",
            "properties": {
                "gmina": {"type": "string"},
                "dzielnica": {"type": "string"},
                "powiat": {"type": "string"},
                "wojewodztwo": {"type": "string"},
            },
            "required": [],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.CHEAP,
        policies=[PolicyTag.FREE_TIER],
        when_to_use="Po potwierdzeniu lokalizacji przez użytkownika",
        when_not_to_use="Bez wcześniejszego search_locations",
        composition=CompositionHint(
            before=["propose_search_preferences"],
        ),
        category="location",
    ),

    ToolDefinitionV3(
        name="get_available_locations",
        description="Lista dostępnych lokalizacji (gminy, miejscowości).",
        input_schema={
            "type": "object",
            "properties": {
                "gmina": {
                    "type": "string",
                    "description": "Filtruj po gminie"
                },
            },
            "required": [],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.CHEAP,
        policies=[PolicyTag.FREE_TIER],
        category="location",
    ),
]


# =============================================================================
# TOOL DEFINITIONS - LEAD
# =============================================================================

TOOLS_V3_LEAD = [
    ToolDefinitionV3(
        name="capture_contact_info",
        description="Zapisz dane kontaktowe użytkownika.",
        input_schema={
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Adres email"
                },
                "phone": {
                    "type": "string",
                    "description": "Numer telefonu"
                },
                "name": {
                    "type": "string",
                    "description": "Imię"
                },
                "notes": {
                    "type": "string",
                    "description": "Dodatkowe notatki"
                },
            },
            "required": [],
        },
        reliability=ReliabilityScore.HIGH,
        cost=CostIndicator.FREE,
        policies=[PolicyTag.FREE_TIER, PolicyTag.PHASE_LEAD],
        when_to_use="Gdy użytkownik podaje dane kontaktowe",
        natural_triggers=["mój email", "mój telefon", "skontaktuj się"],
        category="lead",
    ),
]


# =============================================================================
# GLOBAL REGISTRY
# =============================================================================

def create_tool_registry_v3() -> ToolRegistryV3:
    """Create and populate the V3 tool registry."""
    registry = ToolRegistryV3()

    # Register all tools
    all_tools = (
        TOOLS_V3_PREFERENCE +
        TOOLS_V3_SEARCH +
        TOOLS_V3_CONTEXT +
        TOOLS_V3_LOCATION +
        TOOLS_V3_LEAD
    )

    for tool in all_tools:
        registry.register(tool)

    return registry


# Singleton registry
_registry: Optional[ToolRegistryV3] = None


def get_tool_registry_v3() -> ToolRegistryV3:
    """Get the global V3 tool registry."""
    global _registry
    if _registry is None:
        _registry = create_tool_registry_v3()
    return _registry
