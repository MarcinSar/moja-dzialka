import { useChatStore } from '@/stores/chatStore';

export function ActivityPanel() {
  const { activities, isAgentTyping } = useChatStore();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <h2 className="text-sm font-medium text-white flex items-center gap-2">
          <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          Aktywność Agenta
        </h2>
        <p className="text-xs text-slate-500 mt-1">Podgląd działań w czasie rzeczywistym</p>
      </div>

      {/* Activity Feed */}
      <div className="flex-1 overflow-y-auto p-4">
        {activities.length === 0 && !isAgentTyping ? (
          <div className="text-center py-8">
            <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-slate-800/50 flex items-center justify-center">
              <svg className="w-6 h-6 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <p className="text-sm text-slate-500">
              Rozpocznij rozmowę, aby zobaczyć aktywność agenta
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Current thinking indicator */}
            {isAgentTyping && (
              <ActivityItem
                type="thinking"
                message="Analizuję zapytanie..."
                timestamp={new Date()}
                isActive
              />
            )}

            {/* Activity items */}
            {activities.map((activity) => (
              <ActivityItem
                key={activity.id}
                type={activity.type}
                message={activity.message}
                details={activity.details}
                timestamp={activity.timestamp}
                duration_ms={activity.duration_ms}
              />
            ))}
          </div>
        )}
      </div>

      {/* Stats footer */}
      <div className="p-4 border-t border-border">
        <div className="grid grid-cols-2 gap-4 text-center">
          <div>
            <div className="text-lg font-semibold text-white">
              {activities.filter((a) => a.type === 'success').length}
            </div>
            <div className="text-2xs text-slate-500 uppercase tracking-wider">Operacji</div>
          </div>
          <div>
            <div className="text-lg font-semibold text-white">
              {activities.reduce((sum, a) => sum + (a.duration_ms || 0), 0)}
              <span className="text-xs text-slate-500 ml-1">ms</span>
            </div>
            <div className="text-2xs text-slate-500 uppercase tracking-wider">Czas</div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface ActivityItemProps {
  type: 'thinking' | 'action' | 'success' | 'error';
  message: string;
  details?: string;
  timestamp: Date;
  duration_ms?: number;
  isActive?: boolean;
}

function ActivityItem({ type, message, details, timestamp, duration_ms, isActive }: ActivityItemProps) {
  const typeConfig = {
    thinking: {
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
      ),
      color: 'text-slate-400',
      bgColor: 'bg-slate-700/50',
      prefix: '→',
    },
    action: {
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
      ),
      color: 'text-sky-400',
      bgColor: 'bg-sky-500/10',
      prefix: '→',
    },
    success: {
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ),
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/10',
      prefix: '✓',
    },
    error: {
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      ),
      color: 'text-red-400',
      bgColor: 'bg-red-500/10',
      prefix: '✗',
    },
  };

  const config = typeConfig[type];

  return (
    <div className={`flex items-start gap-2 p-2 rounded-lg ${config.bgColor} ${isActive ? 'animate-pulse' : ''}`}>
      <div className={`mt-0.5 ${config.color}`}>
        {config.icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono ${config.color}`}>
            {config.prefix}
          </span>
          <span className="text-xs text-slate-300 truncate">
            {message}
          </span>
        </div>
        {details && (
          <p className="text-2xs text-slate-500 mt-0.5 truncate">
            {details}
          </p>
        )}
      </div>
      <div className="text-2xs text-slate-600 whitespace-nowrap">
        {duration_ms !== undefined ? (
          <span>{duration_ms}ms</span>
        ) : (
          <span>{formatTime(timestamp)}</span>
        )}
      </div>
    </div>
  );
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('pl-PL', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
