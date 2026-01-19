import { useEffect, useState } from 'react';
import { PhaseTransition } from '@/components/phases/PhaseTransition';
import { useChatStore } from '@/stores/chatStore';
import { useSearchStore } from '@/stores/searchStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { useParcelRevealStore, generateHighlights, generateExplanation } from '@/stores/parcelRevealStore';
import { wsService, parseWSEvent } from '@/services/websocket';
import { listGminy, getSearchStats } from '@/services/api';
import type { SearchResultItem } from '@/types';

function App() {
  const [stats, setStats] = useState<{ total_parcels: number; total_gminy: number } | null>(null);
  const { setConnected, addActivity, startStreaming, appendToLastMessage, finishStreaming } = useChatStore();
  const { setGminy, setLoadingGminy, setMapData } = useSearchStore();
  const { setAvatarMood } = useUIPhaseStore();

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

    // Handle connection changes
    const unsubConnection = wsService.onConnectionChange(setConnected);

    // Handle WebSocket events
    const unsubEvents = wsService.onEvent((event) => {
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

            // Handle execute_search results - show parcel reveal card
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
                  lat?: number;
                  lon?: number;
                  // Backend-generated highlights and explanation
                  highlights?: string[];
                  explanation?: string;
                }>;
                count?: number;
              };

              if (result?.parcels && result.parcels.length > 0) {
                console.log('[Reveal] Received search results with', result.parcels.length, 'parcels');

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
                    centroid_lat: p.lat ?? null,
                    centroid_lon: p.lon ?? null,
                    distance_m: null,
                  };

                  // Use backend-generated highlights/explanation if available, otherwise generate locally
                  return {
                    parcel,
                    explanation: p.explanation || generateExplanation(parcel),
                    highlights: p.highlights || generateHighlights(parcel),
                  };
                });

                // Update the reveal store and show the card
                const revealStore = useParcelRevealStore.getState();
                revealStore.setParcels(parcelsWithExplanations);
                revealStore.showReveal();

                // Set avatar mood
                setAvatarMood('excited');
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
      }
    });

    return () => {
      unsubConnection();
      unsubEvents();
      wsService.disconnect();
    };
  }, []);

  return (
    <div className="h-screen bg-surface overflow-hidden">
      <PhaseTransition stats={stats} />
    </div>
  );
}

export default App;
