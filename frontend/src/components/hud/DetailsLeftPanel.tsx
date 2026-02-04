import { motion } from 'motion/react';
import { Loader2 } from 'lucide-react';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { BasicInfoSection } from '../details/BasicInfoSection';
import { ScoresSection } from '../details/ScoresSection';
import { PogSection } from '../details/PogSection';

export function DetailsLeftPanel() {
  const { parcelData, isLoading, error } = useDetailsPanelStore();

  return (
    <motion.div
      className="absolute left-0 top-14 bottom-20 w-[300px] z-[12]
                 bg-slate-950/70 backdrop-blur-md border-r border-white/5
                 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700/50
                 pointer-events-auto"
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: -300, opacity: 0 }}
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
            <BasicInfoSection parcelData={parcelData} />
            <div className="h-px bg-white/5" />
            <ScoresSection parcelData={parcelData} />
            {parcelData.has_pog && (
              <>
                <div className="h-px bg-white/5" />
                <PogSection parcelData={parcelData} />
              </>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}
