import { Avatar3DSafe } from './Avatar3DSafe';

interface AvatarProps {
  variant?: 'full' | 'compact';
}

export function Avatar(_props: AvatarProps) {
  // Always use full variant - parent controls size via CSS transform scale
  return <Avatar3DSafe />;
}

export { Avatar3DSafe } from './Avatar3DSafe';
