/**
 * AdvancedParcelCard - Enhanced parcel card with progressive disclosure
 *
 * Features:
 * - Compact view by default
 * - Expands on hover/click to show more details
 * - Favorite/Reject feedback buttons
 * - Neighborhood analysis preview
 * - Animated score visualizations
 * - Map preview on hover
 */
import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Heart,
  X as XIcon,
  MapPin,
  Trees,
  Volume2,
  Bus,
  ChevronDown,
  ChevronUp,
  FileText,
  Map as MapIcon,
  Sparkles,
  Star,
} from 'lucide-react';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import type { SearchResultItem } from '@/types';

// API call for feedback
async function submitFeedback(parcelId: string, action: 'favorite' | 'reject') {
  const userId = localStorage.getItem('moja-dzialka-user-id') || 'anonymous';
  try {
    const response = await fetch(`/api/v1/feedback/${encodeURIComponent(parcelId)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': userId,
      },
      body: JSON.stringify({ action }),
    });
    return response.ok;
  } catch {
    console.error('Feedback submission failed');
    return false;
  }
}

interface AdvancedParcelCardProps {
  parcel: SearchResultItem;
  explanation: string;
  highlights: string[];
  index: number;
  isSelected: boolean;
  isSpotlight: boolean;
  onSelect: () => void;
  onHoverStart: () => void;
  onHoverEnd: () => void;
}

export function AdvancedParcelCard({
  parcel,
  explanation,
  highlights,
  index,
  isSelected,
  isSpotlight,
  onSelect,
  onHoverStart,
  onHoverEnd,
}: AdvancedParcelCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [feedbackState, setFeedbackState] = useState<'none' | 'favorited' | 'rejected'>('none');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const openPanel = useDetailsPanelStore((s) => s.openPanel);
  const setAvatarMood = useUIPhaseStore((s) => s.setAvatarMood);

  // Handle favorite/reject
  const handleFeedback = useCallback(
    async (action: 'favorite' | 'reject', e: React.MouseEvent) => {
      e.stopPropagation();
      if (isSubmitting) return;

      setIsSubmitting(true);
      const success = await submitFeedback(parcel.parcel_id, action);

      if (success) {
        setFeedbackState(action === 'favorite' ? 'favorited' : 'rejected');
        setAvatarMood('excited');
        setTimeout(() => setAvatarMood('idle'), 1500);
      }
      setIsSubmitting(false);
    },
    [parcel.parcel_id, isSubmitting, setAvatarMood]
  );

  // Handle details click
  const handleDetailsClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    openPanel(parcel.parcel_id);
  };

  // Toggle expanded state
  const toggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded(!isExpanded);
  };

  // Format location
  const location = parcel.miejscowosc || parcel.gmina || 'Działka';
  const sublocation = parcel.miejscowosc && parcel.gmina ? parcel.gmina : null;

  // Calculate overall score
  const overallScore = Math.round(
    ((parcel.quietness_score || 0) +
      (parcel.nature_score || 0) +
      (parcel.accessibility_score || 0)) /
      3
  );

  return (
    <motion.div
      layout
      onClick={onSelect}
      onHoverStart={onHoverStart}
      onHoverEnd={onHoverEnd}
      className={`
        relative w-[85vw] md:w-[300px] snap-center shrink-0 rounded-2xl cursor-pointer overflow-hidden
        backdrop-blur-xl transition-all duration-300
        ${
          feedbackState === 'favorited'
            ? 'bg-emerald-900/30 border border-emerald-500/30'
            : feedbackState === 'rejected'
            ? 'bg-slate-900/20 opacity-50 border border-slate-700/30'
            : isSelected || isSpotlight
            ? 'bg-white/10 border border-amber-500/30'
            : 'bg-slate-900/40 border border-white/5 hover:bg-white/5'
        }
      `}
      initial={{ opacity: 0, y: 30, scale: 0.95 }}
      animate={{
        opacity: feedbackState === 'rejected' ? 0.5 : 1,
        y: 0,
        scale: 1,
      }}
      whileHover={{
        scale: feedbackState === 'rejected' ? 1 : 1.02,
        transition: { type: 'spring', damping: 20 },
      }}
      style={{
        boxShadow: isSpotlight
          ? '0 8px 40px rgba(245,158,11,0.2), inset 0 1px 0 rgba(255,255,255,0.1)'
          : '0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)',
      }}
    >
      {/* Feedback overlay */}
      <AnimatePresence>
        {feedbackState !== 'none' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={`absolute inset-0 z-20 flex items-center justify-center pointer-events-none ${
              feedbackState === 'favorited' ? 'bg-emerald-500/10' : 'bg-slate-900/50'
            }`}
          >
            {feedbackState === 'favorited' ? (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="flex items-center gap-2 text-emerald-400"
              >
                <Heart className="w-6 h-6 fill-current" />
                <span className="font-medium">Dodano do ulubionych</span>
              </motion.div>
            ) : (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="flex items-center gap-2 text-slate-500"
              >
                <XIcon className="w-6 h-6" />
                <span className="font-medium">Odrzucono</span>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Number badge */}
      <motion.span
        className={`
          absolute -top-3 -left-3 z-10 w-8 h-8 rounded-full
          flex items-center justify-center text-sm font-bold
          shadow-lg transition-colors duration-300
          ${
            feedbackState === 'favorited'
              ? 'bg-emerald-500 text-white'
              : isSpotlight
              ? 'bg-amber-500 text-slate-900'
              : 'bg-slate-700 text-white'
          }
        `}
        animate={isSpotlight ? { scale: [1, 1.1, 1] } : {}}
        transition={{ repeat: isSpotlight ? Infinity : 0, duration: 1.5 }}
      >
        {index + 1}
      </motion.span>

      {/* Main content */}
      <div className="p-5">
        {/* Header with location and overall score */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-white leading-tight truncate">
              {location}
            </h3>
            {sublocation && (
              <div className="flex items-center gap-1 mt-0.5 text-slate-400 text-sm">
                <MapPin className="w-3 h-3" />
                <span>{sublocation}</span>
              </div>
            )}
          </div>
          {/* Overall score badge */}
          <div
            className={`flex items-center gap-1 px-2 py-1 rounded-lg ${
              overallScore >= 70
                ? 'bg-emerald-500/20 text-emerald-400'
                : overallScore >= 50
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-slate-500/20 text-slate-400'
            }`}
          >
            <Star className="w-3 h-3" />
            <span className="text-sm font-medium">{overallScore}</span>
          </div>
        </div>

        {/* Area */}
        <p className="text-slate-400 text-sm mb-4">
          {parcel.area_m2?.toLocaleString('pl-PL')} m²
          {parcel.has_mpzp && (
            <span className="ml-2 text-sky-400">{parcel.mpzp_symbol || 'POG'}</span>
          )}
        </p>

        {/* Score indicators - compact */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <ScoreIndicator
            icon={<Volume2 className="w-3.5 h-3.5" />}
            value={parcel.quietness_score}
            label="Cisza"
            color="teal"
          />
          <ScoreIndicator
            icon={<Trees className="w-3.5 h-3.5" />}
            value={parcel.nature_score}
            label="Natura"
            color="emerald"
          />
          <ScoreIndicator
            icon={<Bus className="w-3.5 h-3.5" />}
            value={parcel.accessibility_score}
            label="Dostęp"
            color="sky"
          />
        </div>

        {/* Highlights */}
        {highlights.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {highlights.slice(0, isExpanded ? 5 : 2).map((highlight) => (
              <span
                key={highlight}
                className="flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-white/5 text-slate-400"
              >
                <Sparkles className="w-2.5 h-2.5 text-amber-400" />
                {highlight}
              </span>
            ))}
            {!isExpanded && highlights.length > 2 && (
              <span className="px-2 py-0.5 text-xs text-slate-500">
                +{highlights.length - 2}
              </span>
            )}
          </div>
        )}

        {/* Expandable section */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              {/* AI Explanation */}
              <div className="mb-4 p-3 rounded-lg bg-white/5">
                <p className="text-sm text-slate-300 leading-relaxed">{explanation}</p>
              </div>

              {/* Coordinates (for map) */}
              {parcel.centroid_lat && parcel.centroid_lon && (
                <div className="flex items-center gap-2 text-xs text-slate-500 mb-4">
                  <MapIcon className="w-3 h-3" />
                  <span>
                    {parcel.centroid_lat.toFixed(5)}, {parcel.centroid_lon.toFixed(5)}
                  </span>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {/* Feedback buttons */}
          {feedbackState === 'none' && (
            <>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                onClick={(e) => handleFeedback('favorite', e)}
                disabled={isSubmitting}
                className="p-3 md:p-2 rounded-lg bg-white/5 text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/20 transition-colors"
              >
                <Heart className="w-4 h-4" />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                onClick={(e) => handleFeedback('reject', e)}
                disabled={isSubmitting}
                className="p-3 md:p-2 rounded-lg bg-white/5 text-slate-400 hover:text-red-400 hover:bg-red-500/20 transition-colors"
              >
                <XIcon className="w-4 h-4" />
              </motion.button>
            </>
          )}

          {/* Details button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleDetailsClick}
            className="flex-1 flex items-center justify-center gap-2 py-3 md:py-2 rounded-lg
                       text-sm font-medium transition-all
                       bg-white/5 hover:bg-sky-500/20 text-slate-400 hover:text-sky-400"
          >
            <FileText className="w-4 h-4" />
            <span>Szczegóły</span>
          </motion.button>

          {/* Expand/collapse toggle */}
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={toggleExpand}
            className="p-3 md:p-2 rounded-lg bg-white/5 text-slate-400 hover:text-white transition-colors"
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
}

// Compact score indicator
function ScoreIndicator({
  icon,
  value,
  label,
  color,
}: {
  icon: React.ReactNode;
  value: number | null;
  label: string;
  color: 'teal' | 'emerald' | 'sky' | 'amber';
}) {
  if (value == null) return null;

  const colorClasses = {
    teal: value >= 70 ? 'text-teal-400 bg-teal-500/20' : 'text-teal-600 bg-teal-500/10',
    emerald:
      value >= 70 ? 'text-emerald-400 bg-emerald-500/20' : 'text-emerald-600 bg-emerald-500/10',
    sky: value >= 70 ? 'text-sky-400 bg-sky-500/20' : 'text-sky-600 bg-sky-500/10',
    amber: value >= 70 ? 'text-amber-400 bg-amber-500/20' : 'text-amber-600 bg-amber-500/10',
  };

  return (
    <div className={`flex flex-col items-center p-2 rounded-lg ${colorClasses[color]}`}>
      {icon}
      <span className="text-xs font-medium mt-1">{Math.round(value)}</span>
      <span className="text-[10px] opacity-60">{label}</span>
    </div>
  );
}
