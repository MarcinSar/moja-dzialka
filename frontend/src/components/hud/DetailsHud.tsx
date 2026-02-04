import { motion, AnimatePresence } from 'motion/react';
import { X } from 'lucide-react';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { useIsMobile } from '@/hooks/useIsMobile';
import { DetailsLeftPanel } from './DetailsLeftPanel';
import { DetailsRightPanel } from './DetailsRightPanel';
import { MobileDetailsSheet } from './MobileDetailsSheet';

export function DetailsHud() {
  const isOpen = useDetailsPanelStore((s) => s.isOpen);
  const parcelId = useDetailsPanelStore((s) => s.parcelId);
  const parcelData = useDetailsPanelStore((s) => s.parcelData);
  const closePanel = useDetailsPanelStore((s) => s.closePanel);
  const isMobile = useIsMobile();

  const location = parcelData?.dzielnica || parcelData?.miejscowosc || parcelData?.gmina || '';

  // Mobile: use bottom sheet
  if (isMobile) {
    return <MobileDetailsSheet />;
  }

  // Desktop: existing L/R panels
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Top bar with parcel ID + location + close button */}
          <motion.div
            className="absolute top-0 left-0 right-0 h-14 z-[12]
                       bg-slate-950/60 backdrop-blur-md border-b border-white/5
                       flex items-center justify-between px-4 pointer-events-auto"
            initial={{ y: -56, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -56, opacity: 0 }}
            transition={{ type: 'spring', damping: 28, stiffness: 200 }}
          >
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-slate-500">{parcelId}</span>
              {location && (
                <>
                  <span className="text-slate-700">|</span>
                  <span className="text-sm text-white font-medium">{location}</span>
                </>
              )}
              {parcelData?.area_m2 && (
                <>
                  <span className="text-slate-700">|</span>
                  <span className="text-sm text-slate-400">
                    {parcelData.area_m2.toLocaleString('pl-PL')} m²
                  </span>
                </>
              )}
            </div>
            <button
              onClick={closePanel}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </motion.div>

          {/* Side panels */}
          <DetailsLeftPanel />
          <DetailsRightPanel />

          {/* Bottom CTA bar */}
          <motion.div
            className="absolute bottom-0 left-[300px] right-[280px] h-16 z-[12]
                       bg-slate-950/60 backdrop-blur-md border-t border-white/5
                       flex items-center justify-center gap-4 pointer-events-auto"
            initial={{ y: 64, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 64, opacity: 0 }}
            transition={{ type: 'spring', damping: 28, stiffness: 200 }}
          >
            <button
              onClick={closePanel}
              className="px-4 py-2 rounded-lg bg-white/5 text-slate-400 text-sm hover:bg-white/10 transition-colors"
            >
              Wróć do wyników
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
