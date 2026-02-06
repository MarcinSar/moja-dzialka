/**
 * FloatingOverlayLayout - Immersive HUD layout with full-screen map
 *
 * All UI elements are rendered as HUD overlays on top of the map.
 * No separate floating windows or modals.
 *
 * Layer structure:
 *  z-[0]  ParticleBackground
 *  z-[1]  Gradient overlays
 *  z-[2]  MapPanelImmersive (full-screen Leaflet with multi-layer support)
 *  z-[3]  Map edge vignette (top/bottom fade)
 *  z-[5]  HudOverlay (pointer-events-none container):
 *           - MapLayerSwitcherHud (top-right)
 *           - ChatHud (left side, floating bubbles)
 *           - DetailsHud (L/R panels when viewing parcel details)
 *           - InputBar (bottom center)
 *  z-[10] Avatar (repositions based on state, always visible, drifts organically)
 *  z-[30] PropertyCardsStrip + results badge
 *  z-[50] Logo + navigation
 */
import { motion, AnimatePresence } from 'motion/react';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { useChatStore } from '@/stores/chatStore';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { useIsMobile } from '@/hooks/useIsMobile';
import { useFloatingDrift } from '@/hooks/useFloatingDrift';
import { MapPanelImmersive } from '../results/MapPanelImmersive';
import { ParticleBackground } from '../effects/ParticleBackground';
import { Avatar } from '../avatar/Avatar';
import { PropertyCardsStrip } from '../results/PropertyCardsStrip';
import { HudOverlay } from '../hud/HudOverlay';

export function FloatingOverlayLayout() {
  const phase = useUIPhaseStore((s) => s.phase);
  const transitionToDiscovery = useUIPhaseStore((s) => s.transitionToDiscovery);

  const messages = useChatStore((s) => s.messages);
  const parcels = useParcelRevealStore((s) => s.parcels);
  const isDetailsOpen = useDetailsPanelStore((s) => s.isOpen);

  const isMobile = useIsMobile();
  const driftRef = useFloatingDrift(22);

  const hasMessages = messages.length > 0;
  const hasResults = parcels.length > 0;
  const showIntro = phase === 'discovery' && !hasMessages;

  return (
    <div className="h-screen w-screen relative overflow-hidden bg-slate-950">
      {/* Layer 0: Particle Background */}
      <ParticleBackground />

      {/* Layer 1: Gradient overlays */}
      <div className="absolute inset-0 bg-gradient-radial from-sky-500/5 via-transparent to-transparent pointer-events-none z-[1]" />

      {/* Layer 2: Full-screen Map */}
      <motion.div
        className="absolute inset-0 z-[2]"
        initial={{ opacity: 0 }}
        animate={{ opacity: hasMessages ? 1 : 0.3 }}
        transition={{ duration: 0.8 }}
      >
        <MapPanelImmersive />
      </motion.div>

      {/* Layer 3: Map edge vignette */}
      <div className="absolute inset-0 pointer-events-none z-[3]">
        <div className="absolute top-0 inset-x-0 h-20 bg-gradient-to-b from-slate-950/80 to-transparent" />
        <div className="absolute bottom-0 inset-x-0 h-32 bg-gradient-to-t from-slate-950/80 to-transparent" />
      </div>

      {/* Layer 5: HUD Overlay (chat, details, input, layer switcher) */}
      <HudOverlay />

      {/* Logo - always visible */}
      <motion.div
        className="absolute top-4 left-4 pt-safe pl-safe z-50 flex items-center gap-2 pointer-events-auto"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center">
          <svg
            className="w-4 h-4 text-white"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
        </div>
        <span className="text-white font-medium text-sm hidden md:inline">moja-dzialka</span>
      </motion.div>

      {/* Back button (when results visible) */}
      <AnimatePresence>
        {hasResults && !isDetailsOpen && (
          <motion.button
            onClick={transitionToDiscovery}
            className="absolute top-4 right-4 pt-safe pr-safe z-50 flex items-center gap-2 px-3 py-2 rounded-xl
                       backdrop-blur-xl bg-slate-900/40 text-slate-400 hover:text-white
                       transition-colors group pointer-events-auto"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            whileHover={{ scale: 1.02 }}
          >
            <svg
              className="w-4 h-4 transition-transform group-hover:-translate-x-1"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            <span className="text-sm hidden md:inline">Nowe wyszukiwanie</span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Avatar - ALWAYS visible, repositions smoothly, drifts organically */}
      <motion.div
        className="absolute z-[10] pointer-events-none"
        animate={
          showIntro
            ? {
                top: '50%',
                left: '50%',
                x: '-50%',
                y: '-55%',
                scale: isMobile ? 0.75 : 1,
                opacity: 1,
              }
            : isMobile
            ? {
                top: '12px',
                left: '50%',
                x: '-50%',
                y: '0%',
                scale: 0.5,
                opacity: 1,
              }
            : isDetailsOpen
            ? {
                top: '80px',
                left: '40px',
                x: '0%',
                y: '0%',
                scale: 0.5,
                opacity: 1,
              }
            : hasResults
            ? {
                top: '30%',
                left: '60px',
                x: '0%',
                y: '0%',
                scale: 0.6,
                opacity: 1,
              }
            : {
                top: '50%',
                left: '60px',
                x: '0%',
                y: '-50%',
                scale: 0.7,
                opacity: 1,
              }
        }
        transition={{ type: 'spring', damping: 28, stiffness: 120, mass: 1 }}
      >
        {/* Inner drift wrapper — continuous organic float via rAF */}
        <div ref={driftRef}>
          <Avatar variant="full" />
        </div>
      </motion.div>

      {/* Intro text - only before first message */}
      <AnimatePresence>
        {showIntro && (
          <motion.div
            className="absolute inset-x-0 z-[10] flex justify-center pointer-events-none"
            style={{ top: isMobile ? '58%' : '62%' }}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 10, opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <div className="text-center space-y-2 px-4">
              <h1 className="text-xl md:text-2xl font-semibold text-white">
                Znajdz swoja wymarzona dzialke
              </h1>
              <p className="text-slate-400 max-w-[90vw] md:max-w-md mx-auto text-sm md:text-base">
                Powiedz mi, czego szukasz - lokalizacja, cisza, natura, dostepnosc.
                Przeszukam tysiace dzialek i znajde idealne dla Ciebie.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Property Cards Strip - left-aligned to avoid overlapping chat on the right */}
      <AnimatePresence>
        {hasResults && !isDetailsOpen && (
          <motion.div
            className={`absolute z-30 pointer-events-auto ${
              isMobile
                ? 'bottom-16 left-0 right-0 px-2'
                : 'bottom-20 left-4 w-full max-w-3xl px-4'
            }`}
            initial={{ y: 60, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 60, opacity: 0 }}
            transition={{ type: 'spring', damping: 25 }}
          >
            <PropertyCardsStrip />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results count badge - left-aligned with cards */}
      <AnimatePresence>
        {hasResults && !isDetailsOpen && (
          <motion.div
            className={`absolute z-30 ${
              isMobile
                ? 'bottom-[180px] left-1/2 -translate-x-1/2'
                : 'bottom-[230px] left-4 ml-4'
            }`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <div className="flex items-center gap-2 px-4 py-2 rounded-full backdrop-blur-xl bg-slate-900/50 pointer-events-auto">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              <span className="text-sm text-slate-300">
                Znaleziono{' '}
                <span className="text-amber-400 font-medium">{parcels.length}</span> dzialek
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
