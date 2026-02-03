import { useEffect, useState, useCallback } from 'react';
import { PhaseTransition } from '@/components/phases/PhaseTransition';
import { LidarLoadingOverlay, Potree3DViewer } from '@/components/potree';
import { useChatStore } from '@/stores/chatStore';
import { useSearchStore } from '@/stores/searchStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { useParcelRevealStore, generateHighlights, generateExplanation } from '@/stores/parcelRevealStore';
import { usePotreeStore } from '@/stores/potreeStore';
import { wsService, parseWSEvent } from '@/services/websocket';
import { listGminy, getSearchStats } from '@/services/api';
import type { SearchResultItem } from '@/types';

function App() {
  const [stats, setStats] = useState<{ total_parcels: number; total_gminy: number } | null>(null);
  const { setConnected, addActivity, startStreaming, appendToLastMessage, finishStreaming } = useChatStore();
  const { setGminy, setLoadingGminy, setMapData } = useSearchStore();
  const { setAvatarMood, setActiveAgent } = useUIPhaseStore();
  const { startLoading, updateProgress, setReady, setError } = usePotreeStore();

  // Handle LiDAR request from ParcelRevealCard
  const handleLidarRequest = useCallback((event: Event) => {
    const { parcelId, lat, lon } = (event as CustomEvent).detail;
    console.log('[LiDAR] Request for parcel:', parcelId, 'at', lat, lon);

    // Send request via WebSocket
    wsService.send({
      type: 'request_lidar',
      parcel_id: parcelId,
      lat,
      lon,
    });
  }, []);

  // Initialize WebSocket and fetch initial data
  useEffect(() => {
    // Fetch gminy list
    setLoadingGminy(true);
    listGminy()
      .then(setGminy)
      .catch((error) => console.error('Failed to load gminy:', error));

    // Fetch stats
    getSearchStats()
      .then(setStats)
      .catch((error) => console.error('Failed to load stats:', error));

    // Connect WebSocket
    wsService.connect();

    // Listen for LiDAR requests from ParcelRevealCard
    window.addEventListener('request-lidar', handleLidarRequest);

    // Handle connection changes
    const unsubConnection = wsService.onConnectionChange(setConnected);

    // Handle WebSocket events
    const unsubEvents = wsService.onEvent((event) => {
      if (!event || !event.type) {
        console.warn('[WS] Received invalid event:', event);
        return;
      }
      const parsed = parseWSEvent(event);

      switch (parsed.type) {
        case 'message':
          if (parsed.message) {
            const { currentStreamingId } = useChatStore.getState();

            if (!parsed.message.is_complete) {
              // Streaming delta - content is just the new chunk
              const delta = parsed.message.content;

              if (!currentStreamingId) {
                // Start new streaming message with this delta
                const msgId = `msg-${Date.now()}`;
                startStreaming(msgId, delta);
              } else {
                // Append delta to existing streaming message
                if (delta) {
                  appendToLastMessage(delta);
                }
              }
              setAvatarMood('speaking');
            } else {
              // Message complete
              if (currentStreamingId) {
                finishStreaming();
              }
              setAvatarMood('idle');
            }
          }
          break;

        case 'activity':
          if (parsed.activity) {
            addActivity({
              id: `act-${Date.now()}`,
              type: 'action',
              message: parsed.activity.action,
              details: parsed.activity.details,
              timestamp: new Date(),
            });
          }
          break;

        case 'tool_call':
          if (parsed.toolCall) {
            addActivity({
              id: `tool-${Date.now()}`,
              type: 'action',
              message: `${parsed.toolCall.tool}`,
              details: JSON.stringify(parsed.toolCall.params),
              timestamp: new Date(),
            });
            // Avatar thinks while tools execute
            setAvatarMood('thinking');
            // Update agent type if provided (v3.0)
            if (parsed.toolCall.agent_type) {
              setActiveAgent(
                parsed.toolCall.agent_type as import('@/stores/uiPhaseStore').AgentType,
                undefined
              );
            }
          }
          break;

        case 'tool_result':
          if (parsed.toolResult) {
            addActivity({
              id: `result-${Date.now()}`,
              type: 'success',
              message: `${parsed.toolResult.tool}: zakończone`,
              details: parsed.toolResult.result_preview,
              timestamp: new Date(),
              duration_ms: parsed.toolResult.duration_ms,
            });

            // Handle execute_search results - transition to immersive search results view
            if (parsed.toolResult.tool === 'execute_search') {
              const result = parsed.toolResult.result as {
                parcels?: Array<{
                  id: string;
                  gmina?: string;
                  miejscowosc?: string;
                  area_m2?: number;
                  quietness_score?: number;
                  nature_score?: number;
                  accessibility_score?: number;
                  has_mpzp?: boolean;
                  mpzp_symbol?: string;
                  centroid_lat?: number;
                  centroid_lon?: number;
                  // Backend-generated highlights and explanation
                  highlights?: string[];
                  explanation?: string;
                }>;
                count?: number;
              };

              if (result?.parcels && result.parcels.length > 0) {
                console.log('[SearchResults] Received', result.parcels.length, 'parcels - transitioning to immersive view');

                // Transform parcels to SearchResultItem format
                const parcelsWithExplanations = result.parcels.map((p) => {
                  const parcel: SearchResultItem = {
                    parcel_id: p.id,
                    rrf_score: 0,
                    sources: [],
                    gmina: p.gmina || null,
                    miejscowosc: p.miejscowosc || null,
                    area_m2: p.area_m2 || null,
                    quietness_score: p.quietness_score ?? null,
                    nature_score: p.nature_score ?? null,
                    accessibility_score: p.accessibility_score ?? null,
                    has_mpzp: p.has_mpzp ?? null,
                    mpzp_symbol: p.mpzp_symbol || null,
                    centroid_lat: p.centroid_lat ?? null,
                    centroid_lon: p.centroid_lon ?? null,
                    distance_m: null,
                  };

                  // Use backend-generated highlights/explanation if available, otherwise generate locally
                  return {
                    parcel,
                    explanation: p.explanation || generateExplanation(parcel),
                    highlights: p.highlights || generateHighlights(parcel),
                  };
                });

                // Update the reveal store with parcels data
                const revealStore = useParcelRevealStore.getState();
                revealStore.setParcels(parcelsWithExplanations);

                // Set avatar mood
                setAvatarMood('excited');

                // Auto-transition to immersive search results view after a short delay
                // This creates a "wow" reveal effect
                setTimeout(() => {
                  const { transitionToSearchResults } = useUIPhaseStore.getState();
                  transitionToSearchResults();
                }, 500);
              }
            }

            // Handle map data from generate_map_data tool
            if (parsed.toolResult.tool === 'generate_map_data') {
              const result = parsed.toolResult.result as { geojson?: unknown; center?: unknown; parcel_count?: number };
              if (result?.geojson) {
                console.log('[Map] Received map data with', result.parcel_count, 'parcels');
                setMapData(result as import('@/types').MapData);
                // Avatar gets excited when results come in
                // (this is also triggered in searchStore but we set it here for immediacy)
                setAvatarMood('excited');
              }
            }
          }
          break;

        case 'thinking':
          addActivity({
            id: `thinking-${Date.now()}`,
            type: 'thinking',
            message: (event.data as { message?: string })?.message || 'Myślę...',
            timestamp: new Date(),
          });
          // Avatar thinks
          setAvatarMood('thinking');
          break;

        case 'session':
          // v2: Session initialized - store user_id/session_id if needed
          if (event.data) {
            const data = event.data as { user_id?: string; session_id?: string; state?: unknown };
            console.log('[WS] Session initialized:', data.user_id, data.session_id);
          }
          break;

        case 'skill_selected':
          // v3: Skill selected by coordinator with agent_type
          {
            const data = event.data as { skill?: string; phase?: string; agent_type?: string };
            console.log('[WS] Skill selected:', data.skill, 'phase:', data.phase, 'agent:', data.agent_type);
            addActivity({
              id: `skill-${Date.now()}`,
              type: 'thinking',
              message: `Faza: ${data.phase || 'unknown'}`,
              details: `Skill: ${data.skill || 'unknown'}`,
              timestamp: new Date(),
            });
            // Update active agent type in store
            if (data.agent_type) {
              setActiveAgent(
                data.agent_type as import('@/stores/uiPhaseStore').AgentType,
                data.skill
              );
            }
          }
          break;

        case 'done':
          // v2: Processing complete
          {
            const data = event.data as { phase?: string; engagement?: string };
            console.log('[WS] Done, phase:', data.phase, 'engagement:', data.engagement);
            // Finish any streaming message
            const { currentStreamingId } = useChatStore.getState();
            if (currentStreamingId) {
              finishStreaming();
            }
            setAvatarMood('idle');
          }
          break;

        case 'error':
          addActivity({
            id: `error-${Date.now()}`,
            type: 'error',
            message: String(event.data),
            timestamp: new Date(),
          });
          // Return to idle on error
          setAvatarMood('idle');
          break;

        // LiDAR events - fields are directly on the event, not in event.data
        case 'lidar_started':
          {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const ev = event as any;
            if (ev.job_id && ev.parcel_id) {
              console.log('[LiDAR] Started job:', ev.job_id);
              startLoading(ev.parcel_id, ev.job_id);
            } else {
              console.warn('[LiDAR] lidar_started missing fields:', event);
            }
          }
          break;

        case 'lidar_progress':
          {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const ev = event as any;
            if (ev.progress !== undefined) {
              console.log('[LiDAR] Progress:', ev.progress, ev.message);
              updateProgress(
                ev.progress,
                ev.message || 'Przetwarzanie...',
                ev.status as 'downloading' | 'converting' | undefined
              );
            } else {
              console.warn('[LiDAR] lidar_progress missing fields:', event);
            }
          }
          break;

        case 'lidar_ready':
          {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const ev = event as any;
            if (ev.potree_url) {
              console.log('[LiDAR] Ready:', ev.potree_url);
              setReady(ev.potree_url, ev.tile_id || '');
            } else {
              console.warn('[LiDAR] lidar_ready missing fields:', event);
            }
          }
          break;

        case 'lidar_error':
          {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const ev = event as any;
            console.error('[LiDAR] Error:', ev.message);
            setError(ev.message || 'Błąd przetwarzania LiDAR');
          }
          break;

        default:
          // Unknown event type - log but don't throw
          console.debug('[WS] Unhandled event type:', parsed.type);
      }
    });

    return () => {
      unsubConnection();
      unsubEvents();
      wsService.disconnect();
      window.removeEventListener('request-lidar', handleLidarRequest);
    };
  }, [handleLidarRequest]);

  return (
    <div className="h-screen bg-surface overflow-hidden">
      <PhaseTransition stats={stats} />

      {/* LiDAR 3D visualization components */}
      <LidarLoadingOverlay />
      <Potree3DViewer />
    </div>
  );
}

export default App;
