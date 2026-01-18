import type {
  SearchPreferences,
  SearchResponse,
  ParcelDetails,
  GminaInfo,
} from '@/types';

const API_BASE = '/api/v1';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || response.statusText);
  }

  return response.json();
}

// ============================================
// Search API
// ============================================

export async function searchParcels(
  preferences: SearchPreferences,
  options: { limit?: number; includeDetails?: boolean } = {}
): Promise<SearchResponse> {
  const params = new URLSearchParams();
  if (options.limit) params.set('limit', options.limit.toString());
  if (options.includeDetails) params.set('include_details', 'true');

  const queryString = params.toString();
  const url = `${API_BASE}/search/${queryString ? `?${queryString}` : ''}`;

  return fetchJson<SearchResponse>(url, {
    method: 'POST',
    body: JSON.stringify(preferences),
  });
}

export async function findSimilarParcels(
  parcelId: string,
  limit: number = 10
): Promise<SearchResponse> {
  return fetchJson<SearchResponse>(
    `${API_BASE}/search/similar/${encodeURIComponent(parcelId)}?limit=${limit}`
  );
}

export async function getParcelDetails(
  parcelId: string,
  includeGeometry: boolean = true
): Promise<ParcelDetails> {
  return fetchJson<ParcelDetails>(
    `${API_BASE}/search/parcel/${encodeURIComponent(parcelId)}?include_geometry=${includeGeometry}`
  );
}

// ============================================
// Gminy API
// ============================================

export async function listGminy(): Promise<string[]> {
  const response = await fetchJson<{ count: number; gminy: string[] }>(
    `${API_BASE}/search/gminy`
  );
  return response.gminy;
}

export async function getGminaInfo(gminaName: string): Promise<GminaInfo> {
  return fetchJson<GminaInfo>(
    `${API_BASE}/search/gmina/${encodeURIComponent(gminaName)}`
  );
}

// ============================================
// Stats API
// ============================================

export interface SearchStats {
  total_parcels: number;
  total_gminy: number;
  data_version: string;
}

export async function getSearchStats(): Promise<SearchStats> {
  return fetchJson<SearchStats>(`${API_BASE}/search/stats`);
}

// ============================================
// Health API
// ============================================

export interface HealthStatus {
  status: 'ok' | 'degraded';
  version: string;
  check_time_ms: number;
  databases: Record<string, { connected: boolean; latency_ms?: number; error?: string }>;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  return fetchJson<HealthStatus>('/health');
}

// ============================================
// Map Data API
// ============================================

export interface MapDataResponse {
  geojson: GeoJSON.FeatureCollection;
  bounds: [[number, number], [number, number]] | null;
  center: [number, number] | null;
  parcel_count: number;
}

export async function getMapData(
  parcelIds: string[],
  includeGeometry: boolean = true
): Promise<MapDataResponse> {
  return fetchJson<MapDataResponse>(`${API_BASE}/search/map`, {
    method: 'POST',
    body: JSON.stringify({
      parcel_ids: parcelIds,
      include_geometry: includeGeometry,
    }),
  });
}
