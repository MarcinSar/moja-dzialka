import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AvatarFull } from '../avatar/AvatarFull';
import { DiscoveryChat } from '../chat/DiscoveryChat';
import { ParticleBackground } from '../effects/ParticleBackground';
import { IntroAnimation } from '../effects/IntroAnimation';
import { ParcelRevealCard } from '../reveal/ParcelRevealCard';
import { useChatStore } from '../../stores/chatStore';
import { useParcelRevealStore } from '../../stores/parcelRevealStore';

type IntroPhase = 'showing' | 'exiting' | 'done';

export function DiscoveryPhase() {
  const messages = useChatStore((s) => s.messages);
  const hasMessages = messages.length > 0;
  const isRevealVisible = useParcelRevealStore((s) => s.isVisible);
  const [introPhase, setIntroPhase] = useState<IntroPhase>('showing');

  const handleIntroStartExit = useCallback(() => {
    setIntroPhase('exiting');
  }, []);

  const handleIntroComplete = useCallback(() => {
    setIntroPhase('done');
  }, []);

  // Skip intro if user already has messages
  const showIntroText = introPhase !== 'done' && !hasMessages;
  const isAvatarExpanding = introPhase === 'exiting' || introPhase === 'done';

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

      {/* Main content container - always present */}
      <div className={`flex-1 flex ${hasMessages ? 'flex-row' : 'flex-col'} items-center justify-center relative z-10 p-4`}>

        {/* Avatar section - always visible */}
        <div
          className={`flex flex-col items-center justify-center ${
            hasMessages ? 'w-1/3 min-w-[280px]' : 'w-full'
          }`}
        >
          {/* Avatar container - simple fade in, no layout animations */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{
              opacity: isAvatarExpanding || hasMessages ? 1 : 0.6,
            }}
            transition={{ duration: 1.5 }}
          >
            <AvatarFull />
          </motion.div>
        </div>

        {/* Chat section - slides in after intro */}
        <motion.div
          className={`${
            hasMessages
              ? 'flex-1 max-w-2xl h-full flex flex-col justify-center'
              : 'w-full max-w-2xl mt-6'
          }`}
          initial={{ opacity: 0, y: 30 }}
          animate={{
            opacity: isAvatarExpanding || hasMessages ? 1 : 0,
            y: isAvatarExpanding || hasMessages ? 0 : 30,
          }}
          transition={{
            duration: 0.6,
            delay: introPhase === 'exiting' ? 0.3 : 0,
            ease: [0.22, 1, 0.36, 1],
          }}
        >
          <DiscoveryChat />
        </motion.div>
      </div>

      {/* Intro text overlay - positioned above avatar */}
      <AnimatePresence>
        {showIntroText && (
          <IntroAnimation
            onStartExit={handleIntroStartExit}
            onComplete={handleIntroComplete}
          />
        )}
      </AnimatePresence>

      {/* Parcel reveal card overlay */}
      <AnimatePresence>
        {isRevealVisible && <ParcelRevealCard />}
      </AnimatePresence>
    </motion.div>
  );
}
