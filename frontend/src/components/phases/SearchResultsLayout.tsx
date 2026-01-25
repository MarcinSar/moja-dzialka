import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { ParticleBackground } from '../effects/ParticleBackground';
import { AvatarFull } from '../avatar/AvatarFull';
import { MapPanelImmersive } from '../results/MapPanelImmersive';
import { PropertyCardsStrip } from '../results/PropertyCardsStrip';
import { ChatFloating } from '../results/ChatFloating';
import { ParcelDetailsPanel } from '../results/ParcelDetailsPanel';

// Avatar floating positions (percentages)
const AVATAR_POSITIONS = [
  { x: 85, y: 5, origin: 'top right' },      // top-right (initial)
  { x: 5, y: 30, origin: 'top left' },        // left-center
  { x: 85, y: 40, origin: 'center right' },   // right-center
  { x: 45, y: 5, origin: 'top center' },      // top-center
  { x: 5, y: 60, origin: 'bottom left' },     // left-lower
];

export function SearchResultsLayout() {
  const parcels = useParcelRevealStore((s) => s.parcels);
  const transitionToDiscovery = useUIPhaseStore((s) => s.transitionToDiscovery);

  // Avatar floating position
  const [avatarPosIndex, setAvatarPosIndex] = useState(0);

  // Randomly change avatar position every 10-15 seconds
  useEffect(() => {
    const changePosition = () => {
      setAvatarPosIndex((prev) => {
        // Pick a different random position
        let next = Math.floor(Math.random() * AVATAR_POSITIONS.length);
        while (next === prev) {
          next = Math.floor(Math.random() * AVATAR_POSITIONS.length);
        }
        return next;
      });
    };

    // Initial delay before first move
    const initialDelay = setTimeout(changePosition, 8000);

    // Then move every 10-15 seconds
    const interval = setInterval(() => {
      changePosition();
    }, 10000 + Math.random() * 5000);

    return () => {
      clearTimeout(initialDelay);
      clearInterval(interval);
    };
  }, []);

  const currentAvatarPos = AVATAR_POSITIONS[avatarPosIndex];

  return (
    <motion.div
      className="h-screen relative overflow-hidden"
      initial={{ opacity: 0, scale: 1.02 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98, filter: 'blur(10px)' }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Continuous particle background - penetrates all layers */}
      <ParticleBackground />

      {/* Subtle radial gradient overlay */}
      <div className="absolute inset-0 bg-gradient-radial from-sky-500/5 via-transparent to-transparent pointer-events-none z-[1]" />

      {/* Back button - top left */}
      <motion.button
        onClick={transitionToDiscovery}
        className="absolute top-6 left-6 z-50 flex items-center gap-2 px-3 py-2 rounded-xl
                   backdrop-blur-xl bg-slate-900/40 text-slate-400 hover:text-white
                   transition-colors group"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.3 }}
        whileHover={{ scale: 1.02 }}
      >
        <svg className="w-4 h-4 transition-transform group-hover:-translate-x-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        <span className="text-sm">Nowe wyszukiwanie</span>
      </motion.button>

      {/* Parcela - floating avatar that moves around */}
      <motion.div
        className="absolute z-50 pointer-events-none"
        initial={{ opacity: 0, scale: 0.5, x: '85%', y: '5%' }}
        animate={{
          opacity: 1,
          scale: 0.55,
          left: `${currentAvatarPos.x}%`,
          top: `${currentAvatarPos.y}%`,
        }}
        transition={{
          opacity: { delay: 0.2, duration: 0.3 },
          scale: { delay: 0.2, type: 'spring', damping: 20 },
          left: { type: 'spring', damping: 25, stiffness: 80 },
          top: { type: 'spring', damping: 25, stiffness: 80 },
        }}
        style={{
          transformOrigin: currentAvatarPos.origin,
          transform: 'translate(-50%, 0)',
        }}
      >
        <AvatarFull />
      </motion.div>

      {/* Map - full screen with fade edges */}
      <div className="absolute inset-0 z-10">
        <MapPanelImmersive />
      </div>

      {/* Property Cards - bottom center, glassmorphism */}
      <AnimatePresence>
        {parcels.length > 0 && (
          <motion.div
            className="absolute bottom-28 left-1/2 -translate-x-1/2 z-30 w-full max-w-4xl px-4"
            initial={{ y: 60, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 60, opacity: 0 }}
            transition={{ delay: 0.4, type: 'spring', damping: 25 }}
          >
            <PropertyCardsStrip />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results count badge - above cards */}
      <AnimatePresence>
        {parcels.length > 0 && (
          <motion.div
            className="absolute bottom-[220px] left-1/2 -translate-x-1/2 z-30"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ delay: 0.3 }}
          >
            <div className="flex items-center gap-2 px-4 py-2 rounded-full backdrop-blur-xl bg-slate-900/50">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              <span className="text-sm text-slate-300">
                Znaleziono <span className="text-amber-400 font-medium">{parcels.length}</span> działek
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Chat - floating input at bottom */}
      <motion.div
        className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[90%] max-w-2xl z-40"
        initial={{ y: 30, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <ChatFloating />
      </motion.div>

      {/* Fade edges to blend map into background */}
      <div className="absolute inset-0 pointer-events-none z-20">
        {/* Top fade */}
        <div className="absolute top-0 inset-x-0 h-32 bg-gradient-to-b from-slate-950 to-transparent" />
        {/* Bottom fade - stronger for cards area */}
        <div className="absolute bottom-0 inset-x-0 h-64 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent" />
        {/* Side fades - subtle */}
        <div className="absolute left-0 inset-y-0 w-16 bg-gradient-to-r from-slate-950/50 to-transparent" />
        <div className="absolute right-0 inset-y-0 w-16 bg-gradient-to-l from-slate-950/50 to-transparent" />
      </div>

      {/* Parcel details panel (modal) */}
      <ParcelDetailsPanel />
    </motion.div>
  );
}
