import { useUIPhaseStore } from '../../stores/uiPhaseStore';
import { AvatarFull } from './AvatarFull';
import { AvatarCompact } from './AvatarCompact';
import { Avatar3DSafe, Avatar3DCompactSafe } from './Avatar3DSafe';

// Feature flag - 3D Avatar using React Three Fiber v8 (compatible with React 18)
const USE_3D_AVATAR = true;

interface AvatarProps {
  variant?: 'full' | 'compact';
  force2D?: boolean; // Force 2D avatar even if 3D is enabled
}

export function Avatar({ variant, force2D = false }: AvatarProps) {
  const phase = useUIPhaseStore((s) => s.phase);

  // Auto-select variant based on phase if not specified
  const resolvedVariant = variant ?? (phase === 'discovery' ? 'full' : 'compact');

  // Use 3D avatar if enabled and not forced to 2D
  if (USE_3D_AVATAR && !force2D) {
    return resolvedVariant === 'full' ? <Avatar3DSafe /> : <Avatar3DCompactSafe />;
  }

  return resolvedVariant === 'full' ? <AvatarFull /> : <AvatarCompact />;
}

// Export all avatar variants
export { AvatarFull } from './AvatarFull';
export { AvatarCompact } from './AvatarCompact';
export { Avatar3DSafe, Avatar3DCompactSafe } from './Avatar3DSafe';
