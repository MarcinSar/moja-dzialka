import { useChatStore } from '@/stores/chatStore';

interface HeaderProps {
  stats: { total_parcels: number; total_gminy: number } | null;
}

export function Header({ stats }: HeaderProps) {
  const isConnected = useChatStore((state) => state.isConnected);

  return (
    <header className="h-14 bg-surface/80 backdrop-blur-sm border-b border-border flex items-center justify-between px-6">
      {/* Logo & Title */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          {/* Logo mark */}
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
            <svg
              className="w-5 h-5 text-slate-900"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
          </div>

          <div>
            <h1 className="text-lg font-semibold text-white tracking-tight">
              moja-działka
            </h1>
            <p className="text-2xs text-slate-500 tracking-wider uppercase">
              Województwo Pomorskie
            </p>
          </div>
        </div>

        {/* Divider */}
        <div className="h-8 w-px bg-border" />

        {/* Stats */}
        {stats && (
          <div className="flex items-center gap-4">
            <div className="coord-display">
              <span className="text-slate-400">{stats.total_parcels.toLocaleString('pl-PL')}</span>
              <span className="ml-1">działek</span>
            </div>
            <div className="coord-display">
              <span className="text-slate-400">{stats.total_gminy}</span>
              <span className="ml-1">gmin</span>
            </div>
          </div>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Connection status */}
        <div className="flex items-center gap-2">
          <div
            className={`status-dot ${
              isConnected ? 'status-dot--active' : 'status-dot--inactive'
            }`}
          />
          <span className="text-xs text-slate-500">
            {isConnected ? 'Połączono' : 'Rozłączono'}
          </span>
        </div>

        {/* Coordinates display (decorative) */}
        <div className="coord-display hidden lg:block">
          54.35°N 18.65°E
        </div>
      </div>
    </header>
  );
}
