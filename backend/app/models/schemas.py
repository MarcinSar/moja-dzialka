"""
Pydantic schemas for API requests and responses.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# CONVERSATION
# =============================================================================

class ChatMessage(BaseModel):
    """User message for chat."""
    content: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Agent response from chat."""
    session_id: str
    message: str
    tool_calls: List[Dict[str, Any]] = []
    map_data: Optional[Dict[str, Any]] = None


class SessionInfo(BaseModel):
    """Session information."""
    session_id: str
    created_at: datetime
    message_count: int
    agent_state: Dict[str, Any]


# =============================================================================
# SEARCH
# =============================================================================

class SearchPreferencesRequest(BaseModel):
    """Search preferences from user."""
    # Location
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    radius_m: float = Field(5000, ge=100, le=50000)
    gmina: Optional[str] = None

    # Area
    min_area_m2: Optional[float] = Field(None, ge=0)
    max_area_m2: Optional[float] = Field(None, ge=0)

    # MPZP
    has_mpzp: Optional[bool] = None
    mpzp_budowlane: Optional[bool] = None
    mpzp_symbol: Optional[str] = None

    # Preference weights (0-1)
    quietness_weight: float = Field(0.5, ge=0, le=1)
    nature_weight: float = Field(0.3, ge=0, le=1)
    accessibility_weight: float = Field(0.2, ge=0, le=1)


class SearchResultItem(BaseModel):
    """Single search result."""
    parcel_id: str
    rrf_score: float
    sources: List[str]

    gmina: Optional[str] = None
    miejscowosc: Optional[str] = None
    area_m2: Optional[float] = None

    quietness_score: Optional[float] = None
    nature_score: Optional[float] = None
    accessibility_score: Optional[float] = None

    has_mpzp: Optional[bool] = None
    mpzp_symbol: Optional[str] = None

    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    distance_m: Optional[float] = None


class SearchResponse(BaseModel):
    """Search response with results."""
    count: int
    total_matching: Optional[int] = None
    results: List[SearchResultItem]
    free_results: int = 3
    requires_payment: bool = False


# =============================================================================
# PARCEL DETAILS
# =============================================================================

class ParcelDetails(BaseModel):
    """Full parcel details."""
    id_dzialki: str
    teryt_powiat: Optional[str] = None

    # Location
    gmina: Optional[str] = None
    dzielnica: Optional[str] = None
    miejscowosc: Optional[str] = None
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None

    # Area and shape
    area_m2: Optional[float] = None
    compactness: Optional[float] = None

    # Land cover
    forest_ratio: Optional[float] = None
    water_ratio: Optional[float] = None
    builtup_ratio: Optional[float] = None

    # Distances
    dist_to_school: Optional[float] = None
    dist_to_shop: Optional[float] = None
    dist_to_hospital: Optional[float] = None
    dist_to_bus_stop: Optional[float] = None
    dist_to_public_road: Optional[float] = None
    dist_to_forest: Optional[float] = None
    dist_to_water: Optional[float] = None
    dist_to_pharmacy: Optional[float] = None

    # Buffer stats
    pct_forest_500m: Optional[float] = None
    pct_water_500m: Optional[float] = None
    count_buildings_500m: Optional[int] = None

    # POG (Plan Ogólny Gminy) - all fields
    has_pog: Optional[bool] = None
    pog_symbol: Optional[str] = None
    pog_nazwa: Optional[str] = None
    pog_oznaczenie: Optional[str] = None
    pog_profil_podstawowy: Optional[str] = None
    pog_profil_podstawowy_nazwy: Optional[str] = None
    pog_profil_dodatkowy: Optional[str] = None
    pog_profil_dodatkowy_nazwy: Optional[str] = None
    pog_maks_intensywnosc: Optional[float] = None
    pog_maks_wysokosc_m: Optional[float] = None
    pog_maks_zabudowa_pct: Optional[float] = None
    pog_min_bio_pct: Optional[float] = None
    is_residential_zone: Optional[bool] = None

    # Composite scores
    quietness_score: Optional[float] = None
    nature_score: Optional[float] = None
    accessibility_score: Optional[float] = None
    has_public_road_access: Optional[bool] = None

    # Building info
    is_built: Optional[bool] = None
    building_count: Optional[int] = None
    building_coverage_pct: Optional[float] = None

    # Categories
    kategoria_ciszy: Optional[str] = None
    kategoria_natury: Optional[str] = None
    kategoria_dostepu: Optional[str] = None
    gestosc_zabudowy: Optional[str] = None

    # Geometry (WGS84 for frontend)
    geometry_wgs84: Optional[Dict[str, Any]] = None


# =============================================================================
# MAP DATA
# =============================================================================

class MapDataRequest(BaseModel):
    """Request for map data generation."""
    parcel_ids: List[str] = Field(..., min_length=1, max_length=100)
    include_geometry: bool = True
    center_on_results: bool = True


class MapDataResponse(BaseModel):
    """GeoJSON data for map visualization."""
    geojson: Dict[str, Any]
    bounds: Optional[List[List[float]]] = None  # [[min_lat, min_lon], [max_lat, max_lon]]
    center: Optional[List[float]] = None  # [lat, lon]
    parcel_count: int


# =============================================================================
# GMINA INFO
# =============================================================================

class GminaInfo(BaseModel):
    """Information about a gmina."""
    name: str
    teryt: Optional[str] = None
    parcel_count: int
    avg_area_m2: Optional[float] = None
    mpzp_coverage_pct: Optional[float] = None
    miejscowosci: List[str] = []


class GminaListResponse(BaseModel):
    """List of gminy."""
    count: int
    gminy: List[str]


# =============================================================================
# MPZP SYMBOLS
# =============================================================================

class MpzpSymbol(BaseModel):
    """MPZP symbol information."""
    symbol: str
    name: str
    description: str
    is_budowlane: bool


class MpzpSymbolsResponse(BaseModel):
    """List of MPZP symbols."""
    count: int
    symbols: List[MpzpSymbol]


# =============================================================================
# ERROR RESPONSES
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# =============================================================================
# LEADS
# =============================================================================

class LeadSubmission(BaseModel):
    """Lead submission for a parcel."""
    parcel_id: str
    name: str
    email: str  # EmailStr not needed here, validation in router
    phone: Optional[str] = None
    interests: List[str] = []


class LeadResponse(BaseModel):
    """Response after lead submission."""
    success: bool
    message: str
    lead_id: Optional[str] = None


# =============================================================================
# NEIGHBORHOOD ANALYSIS (v3.0)
# =============================================================================

class NeighborhoodPOI(BaseModel):
    """Point of interest near a parcel."""
    type: str  # school, bus_stop, shop
    name: Optional[str] = None
    distance_m: float


class NeighborhoodCharacter(BaseModel):
    """Neighborhood character assessment."""
    type: str  # urban, suburban, peripheral, transitional
    description: str


class NeighborhoodDensity(BaseModel):
    """Density metrics for neighborhood."""
    building_pct: float
    residential_pct: float
    avg_parcel_size_m2: Optional[float] = None
    count_buildings_500m: Optional[int] = None
    gestosc_zabudowy: Optional[str] = None


class NeighborhoodEnvironment(BaseModel):
    """Environmental metrics."""
    quietness_score: float
    nature_score: float
    accessibility_score: float


class NeighborhoodScores(BaseModel):
    """Composite neighborhood scores."""
    transport: float
    amenities: float
    overall_livability: float


class NeighborhoodNeighbors(BaseModel):
    """Info about neighboring parcels."""
    adjacent_count: int
    adjacent_parcels: List[Dict[str, Any]] = []
    nearby_poi_count: int


class NeighborhoodAssessment(BaseModel):
    """Human-readable assessment."""
    strengths: List[str] = []
    weaknesses: List[str] = []
    ideal_for: List[str] = []


class NeighborhoodResponse(BaseModel):
    """Complete neighborhood analysis response."""
    parcel_id: str
    district: Optional[str] = None
    city: Optional[str] = None

    character: NeighborhoodCharacter
    density: NeighborhoodDensity
    environment: NeighborhoodEnvironment
    scores: NeighborhoodScores
    neighbors: NeighborhoodNeighbors
    poi: List[NeighborhoodPOI] = []
    assessment: NeighborhoodAssessment
    summary: str

    # Premium feature indicator
    is_premium: bool = True


# =============================================================================
# FEEDBACK (v3.0)
# =============================================================================

class FeedbackAction(str):
    """Feedback action types."""
    FAVORITE = "favorite"
    REJECT = "reject"
    VIEW = "view"
    COMPARE = "compare"


class FeedbackRequest(BaseModel):
    """User feedback on a parcel."""
    action: str = Field(..., pattern="^(favorite|reject|view|compare)$")
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None  # Additional context like comparison_with


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    success: bool
    message: str
    parcel_id: str
    action: str
    patterns_extracted: int = 0  # How many preference patterns were extracted


class UserFeedbackHistory(BaseModel):
    """User's feedback history."""
    user_id: str
    favorites: List[str] = []
    rejections: List[str] = []
    total_views: int = 0
    patterns: Dict[str, Any] = {}


# =============================================================================
# HEALTH CHECK
# =============================================================================

class DatabaseStatus(BaseModel):
    """Status of a database connection."""
    connected: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Detailed health check response."""
    status: str
    version: str
    databases: Dict[str, DatabaseStatus]
