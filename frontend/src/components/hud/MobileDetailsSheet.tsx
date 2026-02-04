import { useRef, useCallback } from 'react';
import { motion, AnimatePresence, useDragControls, PanInfo } from 'motion/react';
import { X, Loader2 } from 'lucide-react';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { BasicInfoSection } from '../details/BasicInfoSection';
import { ScoresSection } from '../details/ScoresSection';
import { PogSection } from '../details/PogSection';
import { DistancesSection } from '../details/DistancesSection';
import { NeighborhoodSection } from '../details/NeighborhoodSection';
import { LeadCaptureSection } from '../details/LeadCaptureSection';

// Snap points as vh fractions
const SNAP_PEEK = 0.45;   // 45vh
const SNAP_FULL = 0.90;   // 90vh

export function MobileDetailsSheet() {
  const isOpen = useDetailsPanelStore((s) => s.isOpen);
  const parcelId = useDetailsPanelStore((s) => s.parcelId);
  const parcelData = useDetailsPanelStore((s) => s.parcelData);
  const isLoading = useDetailsPanelStore((s) => s.isLoading);
  const error = useDetailsPanelStore((s) => s.error);
  const closePanel = useDetailsPanelStore((s) => s.closePanel);

  const dragControls = useDragControls();
  const sheetRef = useRef<HTMLDivElement>(null);

  const location = parcelData?.dzielnica || parcelData?.miejscowosc || parcelData?.gmina || '';
  const windowH = typeof window !== 'undefined' ? window.innerHeight : 800;

  // Initial height is peek (45vh)
  const peekH = windowH * SNAP_PEEK;
  const fullH = windowH * SNAP_FULL;

  const handleDragEnd = useCallback(
    (_e: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      const vy = info.velocity.y;
      const offset = info.offset.y;

      // Swipe down fast or far → dismiss
      if (vy > 500 || offset > peekH * 0.5) {
        closePanel();
        return;
      }

      // Swipe up → expand to full
      if (vy < -300 || offset < -100) {
        if (sheetRef.current) {
          sheetRef.current.style.height = `${fullH}px`;
        }
        return;
      }

      // Otherwise snap to peek
      if (sheetRef.current) {
        sheetRef.current.style.height = `${peekH}px`;
      }
    },
    [closePanel, peekH, fullH]
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="absolute inset-0 z-[11] bg-black/30 pointer-events-auto"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closePanel}
          />

          {/* Bottom sheet */}
          <motion.div
            ref={sheetRef}
            className="absolute bottom-0 left-0 right-0 z-[12] pointer-events-auto
                       bg-slate-950/95 backdrop-blur-xl border-t border-white/10
                       rounded-t-2xl overflow-hidden flex flex-col"
            style={{ height: peekH }}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            drag="y"
            dragControls={dragControls}
            dragConstraints={{ top: -(fullH - peekH), bottom: 0 }}
            dragElastic={0.2}
            onDragEnd={handleDragEnd}
          >
            {/* Drag handle */}
            <div
              className="flex justify-center py-3 cursor-grab active:cursor-grabbing shrink-0"
              onPointerDown={(e) => dragControls.start(e)}
            >
              <div className="w-10 h-1 rounded-full bg-slate-600" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-4 pb-3 border-b border-white/5 shrink-0">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-500 truncate">{parcelId}</span>
                  {location && (
                    <>
                      <span className="text-slate-700">|</span>
                      <span className="text-sm text-white font-medium truncate">{location}</span>
                    </>
                  )}
                </div>
                {parcelData?.area_m2 && (
                  <span className="text-xs text-slate-400 mt-0.5">
                    {parcelData.area_m2.toLocaleString('pl-PL')} m²
                  </span>
                )}
              </div>
              <button
                onClick={closePanel}
                className="p-2.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700/50 pb-safe">
              <div className="p-4 space-y-4">
                {isLoading && (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
                  </div>
                )}

                {error && (
                  <div className="text-center py-8 text-red-400 text-sm">{error}</div>
                )}

                {!isLoading && !error && parcelData && (
                  <>
                    <BasicInfoSection parcelData={parcelData} />
                    <div className="h-px bg-white/5" />
                    <ScoresSection parcelData={parcelData} />
                    {parcelData.has_pog && (
                      <>
                        <div className="h-px bg-white/5" />
                        <PogSection parcelData={parcelData} />
                      </>
                    )}
                    <div className="h-px bg-white/5" />
                    <DistancesSection parcelData={parcelData} />
                    <div className="h-px bg-white/5" />
                    <NeighborhoodSection parcelId={parcelData.id_dzialki} />
                    <div className="h-px bg-white/5" />
                    <LeadCaptureSection parcelId={parcelData.id_dzialki} />
                  </>
                )}
              </div>
            </div>

            {/* Bottom CTA */}
            <div className="shrink-0 px-4 py-3 border-t border-white/5 pb-safe">
              <button
                onClick={closePanel}
                className="w-full py-3 rounded-lg bg-white/5 text-slate-400 text-sm hover:bg-white/10 transition-colors"
              >
                Wróć do wyników
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
