import { AnimatePresence, LayoutGroup } from 'motion/react';
import { useUIPhaseStore } from '../../stores/uiPhaseStore';
import { DiscoveryPhase } from './DiscoveryPhase';
import { ResultsPhase } from './ResultsPhase';

interface PhaseTransitionProps {
  stats: { total_parcels: number; total_gminy: number } | null;
}

export function PhaseTransition({ stats }: PhaseTransitionProps) {
  const phase = useUIPhaseStore((s) => s.phase);

  return (
    <LayoutGroup>
      <AnimatePresence mode="wait">
        {phase === 'discovery' && (
          <DiscoveryPhase key="discovery" />
        )}
        {phase === 'results' && (
          <ResultsPhase key="results" stats={stats} />
        )}
      </AnimatePresence>
    </LayoutGroup>
  );
}
