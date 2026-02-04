/**
 * HudOverlay - Main HUD container that composites all UI elements
 *
 * Everything inside is pointer-events-none by default, with individual
 * interactive elements opting in via pointer-events-auto.
 */
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { useIsMobile } from '@/hooks/useIsMobile';
import { ChatHud } from './ChatHud';
import { InputBar } from './InputBar';
import { DetailsHud } from './DetailsHud';
import { MapLayerSwitcherHud } from './MapLayerSwitcherHud';

export function HudOverlay() {
  const isDetailsOpen = useDetailsPanelStore((s) => s.isOpen);
  const isMobile = useIsMobile();

  return (
    <div className="absolute inset-0 z-[5] pointer-events-none">
      {/* Map layer switcher - desktop: top-right, mobile: bottom-left above map */}
      <div
        className={
          isMobile
            ? 'absolute bottom-20 left-3 z-[6]'
            : 'absolute top-4 right-16 z-[6]'
        }
      >
        <MapLayerSwitcherHud />
      </div>

      {/* Chat messages - hidden when details are open */}
      {!isDetailsOpen && <ChatHud />}

      {/* Details panels (map-integrated) */}
      <DetailsHud />

      {/* Bottom: Input bar - hidden when details are open */}
      {!isDetailsOpen && <InputBar />}
    </div>
  );
}
