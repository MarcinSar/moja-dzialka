import { motion } from 'motion/react';
import { Loader2 } from 'lucide-react';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { DistancesSection } from '../details/DistancesSection';
import { NeighborhoodSection } from '../details/NeighborhoodSection';
import { LeadCaptureSection } from '../details/LeadCaptureSection';

export function DetailsRightPanel() {
  const { parcelData, isLoading, error } = useDetailsPanelStore();

  return (
    <motion.div
      className="absolute right-0 top-14 bottom-20 w-[280px] z-[12]
                 bg-slate-950/70 backdrop-blur-md border-l border-white/5
                 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700/50
                 pointer-events-auto"
      initial={{ x: 280, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 280, opacity: 0 }}
      transition={{ type: 'spring', damping: 28, stiffness: 200 }}
    >
      <div className="p-4 space-y-6">
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
            <DistancesSection parcelData={parcelData} />
            <div className="h-px bg-white/5" />
            <NeighborhoodSection parcelId={parcelData.id_dzialki} />
            <div className="h-px bg-white/5" />
            <LeadCaptureSection parcelId={parcelData.id_dzialki} />
          </>
        )}
      </div>
    </motion.div>
  );
}
