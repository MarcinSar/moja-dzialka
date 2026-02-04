import { motion } from 'motion/react';
import type { ParcelData } from '@/stores/detailsPanelStore';

function ScoreRow({ label, value, color }: { label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    teal: 'from-teal-500 to-teal-400',
    emerald: 'from-emerald-500 to-emerald-400',
    sky: 'from-sky-500 to-sky-400',
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">{label}</span>
        <span className="text-xs font-medium text-white">{Math.round(value)}</span>
      </div>
      <div className="h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className={`h-full rounded-full bg-gradient-to-r ${colorMap[color] || colorMap.sky}`}
        />
      </div>
    </div>
  );
}

export function ScoresSection({ parcelData }: { parcelData: ParcelData }) {
  const hasScores = parcelData.quietness_score != null ||
    parcelData.nature_score != null ||
    parcelData.accessibility_score != null;

  if (!hasScores) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Wskaźniki</h3>
      <div className="space-y-2.5">
        {parcelData.quietness_score != null && (
          <ScoreRow label="Cisza" value={parcelData.quietness_score} color="teal" />
        )}
        {parcelData.nature_score != null && (
          <ScoreRow label="Natura" value={parcelData.nature_score} color="emerald" />
        )}
        {parcelData.accessibility_score != null && (
          <ScoreRow label="Dostępność" value={parcelData.accessibility_score} color="sky" />
        )}
      </div>
    </div>
  );
}
