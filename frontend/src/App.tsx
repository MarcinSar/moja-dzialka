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
          {
            // v4 format: {text: '...', delta: true/false}
            const msgData = event.data as { text?: string; content?: string; delta?: boolean; is_complete?: boolean };
            const text = msgData.text ?? msgData.content ?? '';
            const isDelta = msgData.delta ?? !msgData.is_complete;

            if (text) {
              const { currentStreamingId } = useChatStore.getState();

              if (isDelta) {
                if (!currentStreamingId) {
                  const msgId = `msg-${Date.now()}`;
                  startStreaming(msgId, text);
                } else {
                  appendToLastMessage(text);
                }
                setAvatarMood('speaking');
              } else {
                // Non-streaming: full message at once
                if (!currentStreamingId) {
                  const msgId = `msg-${Date.now()}`;
                  startStreaming(msgId, text);
                } else {
                  appendToLastMessage(text);
                }
              }
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
          {
            // v4 format: {name, input, id} — v2 format: {tool, params, status}
            const tcData = event.data as { name?: string; tool?: string; input?: unknown; params?: unknown; id?: string; agent_type?: string };
            const toolName = tcData.name || tcData.tool || 'unknown';
            const toolParams = tcData.input || tcData.params;
            addActivity({
              id: `tool-${Date.now()}`,
              type: 'action',
              message: toolName,
              details: toolParams ? JSON.stringify(toolParams) : undefined,
              timestamp: new Date(),
            });
            setAvatarMood('thinking');
            if (tcData.agent_type) {
              setActiveAgent(
                tcData.agent_type as import('@/stores/uiPhaseStore').AgentType,
                undefined
              );
            }
          }
          break;

        case 'tool_result':
          {
            // v4 format: {name, result, duration_ms} — v2 format: {tool, result_preview, result, duration_ms}
            const trData = event.data as { name?: string; tool?: string; result?: Record<string, unknown>; result_preview?: string; duration_ms?: number };
            const trToolName = trData.name || trData.tool || 'unknown';
            addActivity({
              id: `result-${Date.now()}`,
              type: 'success',
              message: `${trToolName}: zakończone`,
              details: trData.result_preview,
              timestamp: new Date(),
              duration_ms: trData.duration_ms,
            });

            // Handle search results - v4: search_execute, v2: execute_search
            if (trToolName === 'search_execute' || trToolName === 'execute_search') {
              const result = trData.result as {
                parcels?: Array<{
                  id?: string;
                  id_dzialki?: string;
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
                  highlights?: string[];
                  explanation?: string;
                }>;
                items?: Array<Record<string, unknown>>;
                count?: number;
                total?: number;
              };

              // v4 returns {items, total, ...} from JSONL pagination
              const parcels = result?.parcels || (result?.items as typeof result.parcels);

              if (parcels && parcels.length > 0) {
                console.log('[SearchResults] Received', parcels.length, 'parcels - transitioning to immersive view');

                const parcelsWithExplanations = parcels.map((p) => {
                  const parcel: SearchResultItem = {
                    parcel_id: p.id || p.id_dzialki || '',
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

                  return {
                    parcel,
                    explanation: p.explanation || generateExplanation(parcel),
                    highlights: p.highlights || generateHighlights(parcel),
                  };
                });

                const revealStore = useParcelRevealStore.getState();
                revealStore.setParcels(parcelsWithExplanations);
                setAvatarMood('excited');

                setTimeout(() => {
                  const { transitionToSearchResults } = useUIPhaseStore.getState();
                  transitionToSearchResults();
                }, 500);
              }
            }

            // Handle map data - v4: market_map, v2: generate_map_data
            if (trToolName === 'market_map' || trToolName === 'generate_map_data') {
              const result = trData.result as { geojson?: unknown; center?: unknown; parcel_count?: number };
              if (result?.geojson) {
                console.log('[Map] Received map data with', result.parcel_count, 'parcels');
                setMapData(result as import('@/types').MapData);
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
          // v4: {session_id}, v2: {phase, engagement}
          {
            const data = event.data as { session_id?: string; phase?: string; engagement?: string };
            console.log('[WS] Done, session:', data.session_id);
            // Finish any streaming message
            const { currentStreamingId } = useChatStore.getState();
            if (currentStreamingId) {
              finishStreaming();
            }
            setAvatarMood('idle');
          }
          break;

        case 'error':
          {
            const errData = event.data as { message?: string } | string;
            const errMsg = typeof errData === 'string' ? errData : errData?.message || 'Unknown error';
            addActivity({
              id: `error-${Date.now()}`,
              type: 'error',
              message: errMsg,
              timestamp: new Date(),
            });
            // Finish streaming on error and return to idle
            const { currentStreamingId: errStreamId } = useChatStore.getState();
            if (errStreamId) {
              finishStreaming();
            }
            setAvatarMood('idle');
          }
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
