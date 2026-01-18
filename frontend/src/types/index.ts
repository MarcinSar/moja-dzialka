// ============================================
// API Types
// ============================================

export interface SearchPreferences {
  lat?: number;
  lon?: number;
  radius_m?: number;
  gmina?: string;
  min_area_m2?: number;
  max_area_m2?: number;
  has_mpzp?: boolean;
  mpzp_budowlane?: boolean;
  mpzp_symbol?: string;
  quietness_weight?: number;
  nature_weight?: number;
  accessibility_weight?: number;
}

export interface SearchResultItem {
  parcel_id: string;
  rrf_score: number;
  sources: string[];
  gmina: string | null;
  miejscowosc: string | null;
  area_m2: number | null;
  quietness_score: number | null;
  nature_score: number | null;
  accessibility_score: number | null;
  has_mpzp: boolean | null;
  mpzp_symbol: string | null;
  centroid_lat: number | null;
  centroid_lon: number | null;
  distance_m: number | null;
}

export interface SearchResponse {
  count: number;
  total_matching: number;
  results: SearchResultItem[];
  free_results: number;
  requires_payment: boolean;
}

export interface ParcelDetails {
  id_dzialki: string;
  teryt_powiat?: string;
  gmina: string;
  miejscowosc?: string;
  centroid_lat: number;
  centroid_lon: number;
  area_m2: number;
  compactness?: number;
  forest_ratio?: number;
  water_ratio?: number;
  builtup_ratio?: number;
  dist_to_school?: number;
  dist_to_shop?: number;
  dist_to_hospital?: number;
  dist_to_bus_stop?: number;
  dist_to_public_road?: number;
  dist_to_forest?: number;
  dist_to_water?: number;
  pct_forest_500m?: number;
  pct_water_500m?: number;
  count_buildings_500m?: number;
  has_mpzp: boolean;
  mpzp_symbol?: string;
  mpzp_przeznaczenie?: string;
  mpzp_budowlane?: boolean;
  quietness_score: number;
  nature_score: number;
  accessibility_score: number;
  has_public_road_access?: boolean;
  geometry_wgs84?: GeoJSON.Geometry;
}

export interface GminaInfo {
  name: string;
  teryt?: string;
  parcel_count: number;
  avg_area_m2?: number;
  mpzp_coverage_pct?: number;
  miejscowosci: string[];
}

// ============================================
// Chat Types
// ============================================

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface AgentActivity {
  id: string;
  type: 'thinking' | 'action' | 'success' | 'error';
  message: string;
  timestamp: Date;
  duration_ms?: number;
  details?: string;
}

export interface ConversationState {
  messages: ChatMessage[];
  activities: AgentActivity[];
  isConnected: boolean;
  isAgentTyping: boolean;
  currentSearch?: SearchPreferences;
}

// ============================================
// WebSocket Events
// ============================================

export type WSEventType = 'message' | 'activity' | 'tool_call' | 'tool_result' | 'search_results' | 'error' | 'thinking' | 'done' | 'session';

export interface WSEvent {
  type: WSEventType;
  timestamp?: number;
  data: unknown;
}

export interface WSMessageData {
  role: 'assistant';
  content: string;
  is_complete: boolean;
}

export interface WSActivityData {
  action: string;
  details?: string;
  progress?: number;
}

export interface WSToolCallData {
  tool: string;
  params: Record<string, unknown>;
  status: 'started' | 'completed' | 'failed';
  duration_ms?: number;
  result_count?: number;
}

export interface WSToolResultData {
  tool: string;
  duration_ms?: number;
  result_preview?: string;
  result?: Record<string, unknown>;
}

export interface MapGeoJSON {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: GeoJSON.Geometry;
    properties: {
      id: string;
      gmina?: string;
      area_m2?: number;
      quietness_score?: number;
      nature_score?: number;
      has_mpzp?: boolean;
    };
  }>;
}

export interface MapData {
  geojson: MapGeoJSON;
  center: { lat: number; lon: number } | null;
  parcel_count: number;
}

// ============================================
// UI State Types
// ============================================

export interface MapViewState {
  center: [number, number];
  zoom: number;
}

export interface UIState {
  selectedParcelId: string | null;
  hoveredParcelId: string | null;
  isPanelCollapsed: {
    chat: boolean;
    activity: boolean;
  };
  mapView: MapViewState;
}
