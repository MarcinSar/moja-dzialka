import { motion } from 'motion/react';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { FileText } from 'lucide-react';

// Animation variants for staggered entry
const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
};

const cardVariants = {
  hidden: { y: 30, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { type: 'spring' as const, damping: 20, stiffness: 100 },
  },
};

export function PropertyCardsStrip() {
  const parcels = useParcelRevealStore((s) => s.parcels);
  const currentIndex = useParcelRevealStore((s) => s.currentIndex);
  const goToParcel = useParcelRevealStore((s) => s.goToParcel);
  const spotlightParcelId = useUIPhaseStore((s) => s.spotlightParcelId);
  const setSpotlightParcel = useUIPhaseStore((s) => s.setSpotlightParcel);
  const setAvatarMood = useUIPhaseStore((s) => s.setAvatarMood);

  // Only show first 3 parcels
  const displayParcels = parcels.slice(0, 3);

  if (displayParcels.length === 0) return null;

  return (
    <motion.div
      className="flex justify-center gap-4"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {displayParcels.map((item, index) => (
        <PropertyCard
          key={item.parcel.parcel_id}
          item={item}
          index={index}
          isSelected={currentIndex === index}
          isSpotlight={spotlightParcelId === item.parcel.parcel_id}
          onSelect={() => goToParcel(index)}
          onHoverStart={() => {
            setSpotlightParcel(item.parcel.parcel_id);
            setAvatarMood('excited');
          }}
          onHoverEnd={() => {
            setSpotlightParcel(null);
            setAvatarMood('idle');
          }}
        />
      ))}
    </motion.div>
  );
}

interface PropertyCardProps {
  item: {
    parcel: {
      parcel_id: string;
      miejscowosc?: string | null;
      gmina?: string | null;
      area_m2?: number | null;
      quietness_score?: number | null;
      nature_score?: number | null;
      accessibility_score?: number | null;
      centroid_lat?: number | null;
      centroid_lon?: number | null;
    };
    explanation: string;
    highlights: string[];
  };
  index: number;
  isSelected: boolean;
  isSpotlight: boolean;
  onSelect: () => void;
  onHoverStart: () => void;
  onHoverEnd: () => void;
}

function PropertyCard({ item, index, isSelected, isSpotlight, onSelect, onHoverStart, onHoverEnd }: PropertyCardProps) {
  const { parcel, highlights } = item;
  const openPanel = useDetailsPanelStore((s) => s.openPanel);

  // Open details panel
  const handleDetailsClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    openPanel(parcel.parcel_id);
  };

  return (
    <motion.div
      variants={cardVariants}
      onClick={onSelect}
      onHoverStart={onHoverStart}
      onHoverEnd={onHoverEnd}
      className={`
        relative w-[280px] p-5 rounded-2xl cursor-pointer
        backdrop-blur-xl transition-all duration-300
        ${isSelected || isSpotlight
          ? 'bg-white/10 shadow-[0_0_40px_rgba(245,158,11,0.15)]'
          : 'bg-slate-900/40 hover:bg-white/5'
        }
      `}
      whileHover={{
        scale: 1.02,
        transition: { type: 'spring', damping: 20 },
      }}
      style={{
        boxShadow: isSpotlight
          ? '0 8px 40px rgba(245,158,11,0.2), inset 0 1px 0 rgba(255,255,255,0.1)'
          : '0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)',
      }}
    >
      {/* Number badge */}
      <motion.span
        className={`
          absolute -top-3 -left-3 w-8 h-8 rounded-full
          flex items-center justify-center text-sm font-bold
          shadow-lg transition-colors duration-300
          ${isSpotlight
            ? 'bg-amber-500 text-slate-900'
            : 'bg-slate-700 text-white'
          }
        `}
        animate={isSpotlight ? { scale: [1, 1.1, 1] } : {}}
        transition={{ repeat: isSpotlight ? Infinity : 0, duration: 1.5 }}
      >
        {index + 1}
      </motion.span>

      {/* Location */}
      <div className="mb-3">
        <h3 className="text-lg font-semibold text-white leading-tight">
          {parcel.miejscowosc || parcel.gmina || 'Działka'}
        </h3>
        <p className="text-slate-400 text-sm mt-1">
          {parcel.area_m2?.toLocaleString('pl-PL')} m²
        </p>
      </div>

      {/* Score bars - minimalist */}
      <div className="space-y-2 mb-4">
        {parcel.quietness_score != null && (
          <ScoreBar
            label="Cisza"
            value={parcel.quietness_score}
            color="teal"
            isActive={isSpotlight}
          />
        )}
        {parcel.nature_score != null && (
          <ScoreBar
            label="Natura"
            value={parcel.nature_score}
            color="emerald"
            isActive={isSpotlight}
          />
        )}
      </div>

      {/* Highlights - subtle tags */}
      {highlights.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {highlights.slice(0, 2).map((highlight) => (
            <span
              key={highlight}
              className="px-2 py-0.5 rounded-md text-xs bg-white/5 text-slate-400"
            >
              {highlight}
            </span>
          ))}
        </div>
      )}

      {/* Details button */}
      <button
        onClick={handleDetailsClick}
        className="w-full flex items-center justify-center gap-2 py-2 rounded-lg
                   text-sm font-medium transition-all
                   bg-white/5 hover:bg-sky-500/20 text-slate-400 hover:text-sky-400"
      >
        <FileText className="w-4 h-4" />
        <span>Szczegóły</span>
      </button>
    </motion.div>
  );
}

// Minimalist score bar component
function ScoreBar({
  label,
  value,
  color,
  isActive,
}: {
  label: string;
  value: number;
  color: 'teal' | 'emerald' | 'amber';
  isActive: boolean;
}) {
  const colorClasses = {
    teal: isActive ? 'from-teal-400 to-teal-300' : 'from-teal-600 to-teal-500',
    emerald: isActive ? 'from-emerald-400 to-emerald-300' : 'from-emerald-600 to-emerald-500',
    amber: isActive ? 'from-amber-400 to-amber-300' : 'from-amber-600 to-amber-500',
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-12">{label}</span>
      <div className="flex-1 h-1 bg-slate-700/50 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.3 }}
          className={`h-full rounded-full bg-gradient-to-r ${colorClasses[color]}`}
        />
      </div>
      <span className="text-xs text-slate-500 w-6 text-right">{Math.round(value)}</span>
    </div>
  );
}
