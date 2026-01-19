import { motion, AnimatePresence } from 'motion/react';
import { AvatarFull } from '../avatar/AvatarFull';
import { DiscoveryChat } from '../chat/DiscoveryChat';
import { ParticleBackground } from '../effects/ParticleBackground';
import { ParcelRevealCard } from '../reveal/ParcelRevealCard';
import { useChatStore } from '../../stores/chatStore';
import { useParcelRevealStore } from '../../stores/parcelRevealStore';

export function DiscoveryPhase() {
  const messages = useChatStore((s) => s.messages);
  const hasMessages = messages.length > 0;
  const isRevealVisible = useParcelRevealStore((s) => s.isVisible);

  return (
    <motion.div
      className="h-screen flex flex-col relative overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Particle background */}
      <ParticleBackground />

      {/* Gradient overlays */}
      <div className="absolute inset-0 bg-gradient-radial from-sky-500/5 via-transparent to-transparent pointer-events-none" />

      {/* Logo in corner */}
      <motion.div
        className="absolute top-4 left-4 z-20 flex items-center gap-2"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
      >
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center">
          <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
        </div>
        <span className="text-white font-medium text-sm">moja-działka</span>
      </motion.div>

      {/* Main content - horizontal split when chatting */}
      <div className={`flex-1 flex ${hasMessages ? 'flex-row' : 'flex-col'} items-center justify-center relative z-10 p-4`}>

        {/* Avatar section - fixed size, stays visible */}
        <motion.div
          className={`flex flex-col items-center justify-center ${
            hasMessages ? 'w-1/3 min-w-[280px]' : 'w-full'
          }`}
          layout
          transition={{ duration: 0.5, ease: "easeInOut" }}
        >
          {/* Avatar - smaller when chatting */}
          <motion.div
            className={hasMessages ? 'scale-75' : 'scale-100'}
            style={{ transformOrigin: 'center center' }}
            layout
            transition={{ duration: 0.5 }}
          >
            <AvatarFull />
          </motion.div>

          {/* Title - hide when chatting */}
          <AnimatePresence>
            {!hasMessages && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20, height: 0 }}
                transition={{ duration: 0.3 }}
                className="text-center mt-4"
              >
                <h1 className="text-2xl font-semibold text-white mb-2">
                  Znajdę Twoją idealną działkę
                </h1>
                <p className="text-slate-400">
                  Powiedz mi, czego szukasz na Pomorzu
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Stats - hide when chatting */}
          <AnimatePresence>
            {!hasMessages && (
              <motion.div
                className="mt-4 flex items-center justify-center gap-2"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <span className="px-3 py-1.5 rounded-full bg-surface-elevated/50 backdrop-blur-sm border border-slate-700/30 text-xs text-slate-400">
                  <span className="text-cyan-400 font-medium">1.3M</span> działek
                </span>
                <span className="px-3 py-1.5 rounded-full bg-surface-elevated/50 backdrop-blur-sm border border-slate-700/30 text-xs text-slate-400">
                  <span className="text-blue-400 font-medium">123</span> gminy
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Chat section */}
        <motion.div
          className={`${
            hasMessages
              ? 'flex-1 max-w-2xl h-full flex flex-col justify-center'
              : 'w-full max-w-2xl mt-6'
          }`}
          layout
          transition={{ duration: 0.5, ease: "easeInOut" }}
        >
          <DiscoveryChat />
        </motion.div>
      </div>

      {/* Parcel reveal card overlay */}
      <AnimatePresence>
        {isRevealVisible && <ParcelRevealCard />}
      </AnimatePresence>

    </motion.div>
  );
}
