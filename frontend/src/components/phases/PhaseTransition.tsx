import { AnimatePresence, LayoutGroup } from 'motion/react';
import { useUIPhaseStore } from '../../stores/uiPhaseStore';
import { FloatingOverlayLayout } from '../layout/FloatingOverlayLayout';
import { ResultsPhase } from './ResultsPhase';

// Legacy imports - kept for potential fallback
// import { DiscoveryPhase } from './DiscoveryPhase';
// import { SearchResultsLayout } from './SearchResultsLayout';

interface PhaseTransitionProps {
  stats: { total_parcels: number; total_gminy: number } | null;
}

/**
 * PhaseTransition - Main layout switcher
 *
 * v3.0: Uses unified FloatingOverlayLayout for discovery and search_results phases.
 * The layout handles phase transitions internally with smooth animations.
 */
export function PhaseTransition({ stats }: PhaseTransitionProps) {
  const phase = useUIPhaseStore((s) => s.phase);

  return (
    <LayoutGroup>
      <AnimatePresence mode="wait">
        {/* Use unified FloatingOverlayLayout for discovery and search_results */}
        {(phase === 'discovery' || phase === 'search_results') && (
          <FloatingOverlayLayout key="floating-overlay" />
        )}

        {/* Results phase uses dedicated layout (for detailed parcel view) */}
        {phase === 'results' && (
          <ResultsPhase key="results" stats={stats} />
        )}
      </AnimatePresence>
    </LayoutGroup>
  );
}
