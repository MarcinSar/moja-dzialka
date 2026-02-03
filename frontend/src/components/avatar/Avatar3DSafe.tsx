/**
 * Avatar3DSafe - Safe wrapper for 3D avatar with error boundary and lazy loading
 *
 * This prevents the entire app from crashing if WebGL or Three.js fails.
 */
import { Suspense, lazy, useState, useEffect, Component, ReactNode } from 'react';
import { useUIPhaseStore, AvatarMood } from '@/stores/uiPhaseStore';

// Lazy load the face mesh avatar (wireframe face recognition style)
const Avatar3DCanvas = lazy(() => import('./FaceMeshAvatar'));

// Error boundary to catch WebGL/Three.js errors
interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class Avatar3DErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: ReactNode; fallback: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[Avatar3D] Error caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

// Loading placeholder
function Avatar3DLoading({ compact }: { compact?: boolean }) {
  const size = compact ? 'w-12 h-12' : 'w-[200px] h-[200px]';

  return (
    <div className={`${size} flex items-center justify-center`}>
      <div className="relative">
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500/30 to-blue-500/30 animate-pulse" />
        <div className="absolute inset-0 rounded-full border-2 border-cyan-400/30 animate-spin" style={{ animationDuration: '3s' }} />
      </div>
    </div>
  );
}

// Fallback 2D avatar when 3D fails
function Avatar2DFallback({ compact }: { compact?: boolean }) {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';
  const size = compact ? 'w-12 h-12' : 'w-[120px] h-[120px]';

  const moodColors: Record<AvatarMood, string> = {
    idle: 'from-cyan-400 to-blue-500',
    thinking: 'from-blue-400 to-indigo-500',
    speaking: 'from-cyan-300 to-teal-500',
    excited: 'from-violet-400 to-purple-500',
  };

  return (
    <div className="flex flex-col items-center">
      <div className={`${size} relative`}>
        {/* Glow */}
        <div
          className={`absolute inset-[-20%] rounded-full bg-gradient-to-br ${moodColors[mood]} opacity-20 blur-xl`}
        />
        {/* Core */}
        <div
          className={`relative w-full h-full rounded-full bg-gradient-to-br ${moodColors[mood]} shadow-lg`}
          style={{
            animation: mood === 'speaking'
              ? 'pulse 0.5s ease-in-out infinite'
              : mood === 'thinking'
              ? 'pulse 2s ease-in-out infinite'
              : 'none'
          }}
        >
          {/* Inner highlight */}
          <div className="absolute inset-2 rounded-full bg-gradient-to-br from-white/20 to-transparent" />

          {/* Animated ring */}
          <div
            className="absolute inset-[-4px] rounded-full border-2 border-white/20"
            style={{ animation: 'spin 8s linear infinite' }}
          />
        </div>
      </div>

      {/* Status (full size only) */}
      {!compact && (
        <div className="mt-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-xs font-mono tracking-widest uppercase text-cyan-400/70">
            {mood === 'speaking' ? 'TRANSMITTING' :
             mood === 'thinking' ? 'PROCESSING' :
             mood === 'excited' ? 'READY' : 'LISTENING'}
          </span>
        </div>
      )}
    </div>
  );
}

// Check WebGL support
function isWebGLSupported(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch (e) {
    return false;
  }
}

// Main safe wrapper
export function Avatar3DSafe({ compact = false }: { compact?: boolean }) {
  const [webglSupported, setWebglSupported] = useState<boolean | null>(null);

  useEffect(() => {
    setWebglSupported(isWebGLSupported());
  }, []);

  // Still checking
  if (webglSupported === null) {
    return <Avatar3DLoading compact={compact} />;
  }

  // No WebGL - use 2D fallback
  if (!webglSupported) {
    console.warn('[Avatar3D] WebGL not supported, using 2D fallback');
    return <Avatar2DFallback compact={compact} />;
  }

  // Try 3D with error boundary
  return (
    <Avatar3DErrorBoundary fallback={<Avatar2DFallback compact={compact} />}>
      <Suspense fallback={<Avatar3DLoading compact={compact} />}>
        <Avatar3DCanvas compact={compact} />
      </Suspense>
    </Avatar3DErrorBoundary>
  );
}

export function Avatar3DCompactSafe() {
  return <Avatar3DSafe compact />;
}
