import { motion } from 'motion/react';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { useIsMobile } from '@/hooks/useIsMobile';
import { AdvancedParcelCard } from './AdvancedParcelCard';

// Animation variants for staggered entry
const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.3,
    },
  },
};

export function PropertyCardsStrip() {
  const parcels = useParcelRevealStore((s) => s.parcels);
  const currentIndex = useParcelRevealStore((s) => s.currentIndex);
  const goToParcel = useParcelRevealStore((s) => s.goToParcel);
  const spotlightParcelId = useUIPhaseStore((s) => s.spotlightParcelId);
  const setSpotlightParcel = useUIPhaseStore((s) => s.setSpotlightParcel);
  const setAvatarMood = useUIPhaseStore((s) => s.setAvatarMood);
  const isMobile = useIsMobile();

  // Only show first 3 parcels (freemium)
  const displayParcels = parcels.slice(0, 3);

  if (displayParcels.length === 0) return null;

  return (
    <motion.div
      className={
        isMobile
          ? 'flex gap-3 overflow-x-auto snap-x snap-mandatory pb-4 px-2 -mx-2 scrollbar-thin'
          : 'flex justify-center gap-4 flex-wrap'
      }
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {displayParcels.map((item, index) => (
        <AdvancedParcelCard
          key={item.parcel.parcel_id}
          parcel={item.parcel}
          explanation={item.explanation}
          highlights={item.highlights}
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
