import { useEffect, useState } from 'react';
import { ChatPanel } from '@/components/ChatPanel';
import { MapPanel } from '@/components/MapPanel';
import { ActivityPanel } from '@/components/ActivityPanel';
import { Header } from '@/components/Header';
import { useChatStore } from '@/stores/chatStore';
import { useSearchStore } from '@/stores/searchStore';
import { wsService, parseWSEvent } from '@/services/websocket';
import { listGminy, getSearchStats } from '@/services/api';

function App() {
  const [stats, setStats] = useState<{ total_parcels: number; total_gminy: number } | null>(null);
  const { setConnected, addMessage, updateMessage, addActivity, setAgentTyping } = useChatStore();
  const { setGminy, setLoadingGminy, setMapData } = useSearchStore();

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
            const msgId = `msg-${Date.now()}`;
            if (!parsed.message.is_complete) {
              // Streaming message - add or update
              addMessage({
                id: msgId,
                role: 'assistant',
                content: parsed.message.content,
                timestamp: new Date(),
                isStreaming: true,
              });
              setAgentTyping(true);
            } else {
              // Complete message
              updateMessage(msgId, parsed.message.content, true);
              setAgentTyping(false);
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

            // Handle map data from generate_map_data tool
            if (parsed.toolResult.tool === 'generate_map_data') {
              const result = parsed.toolResult.result as { geojson?: unknown; center?: unknown; parcel_count?: number };
              if (result?.geojson) {
                console.log('[Map] Received map data with', result.parcel_count, 'parcels');
                setMapData(result as import('@/types').MapData);
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
          break;

        case 'error':
          addActivity({
            id: `error-${Date.now()}`,
            type: 'error',
            message: String(event.data),
            timestamp: new Date(),
          });
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
    <div className="h-screen flex flex-col bg-slate-950 overflow-hidden">
      {/* Header */}
      <Header stats={stats} />

      {/* Main content - Split layout */}
      <main className="flex-1 flex overflow-hidden">
        {/* Chat Panel - 30% */}
        <div className="w-[30%] min-w-[320px] border-r border-border flex flex-col">
          <ChatPanel />
        </div>

        {/* Map + Results Panel - 50% */}
        <div className="flex-1 flex flex-col">
          <MapPanel />
        </div>

        {/* Activity Panel - 20% */}
        <div className="w-[20%] min-w-[240px] border-l border-border flex flex-col">
          <ActivityPanel />
        </div>
      </main>
    </div>
  );
}

export default App;
