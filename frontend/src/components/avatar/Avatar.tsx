import { useUIPhaseStore } from '../../stores/uiPhaseStore';
import { AvatarFull } from './AvatarFull';
import { AvatarCompact } from './AvatarCompact';

interface AvatarProps {
  variant?: 'full' | 'compact';
}

export function Avatar({ variant }: AvatarProps) {
  const phase = useUIPhaseStore((s) => s.phase);

  // Auto-select variant based on phase if not specified
  const resolvedVariant = variant ?? (phase === 'discovery' ? 'full' : 'compact');

  return resolvedVariant === 'full' ? <AvatarFull /> : <AvatarCompact />;
}

export { AvatarFull } from './AvatarFull';
export { AvatarCompact } from './AvatarCompact';
