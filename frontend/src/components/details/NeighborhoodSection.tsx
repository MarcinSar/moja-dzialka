import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { MapPin, ChevronDown } from 'lucide-react';
import { NeighborhoodAnalysis } from '../results/NeighborhoodAnalysis';

export function NeighborhoodSection({ parcelId }: { parcelId: string }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="space-y-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between py-2 text-left hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center gap-2">
          <MapPin className="w-3.5 h-3.5 text-sky-400" />
          <span className="text-xs font-medium text-slate-300">Analiza okolicy</span>
        </div>
        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          className="text-slate-500"
        >
          <ChevronDown className="w-3.5 h-3.5" />
        </motion.div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <NeighborhoodAnalysis parcelId={parcelId} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
