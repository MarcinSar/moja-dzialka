import { motion } from 'motion/react';
import { useUIPhaseStore } from '../../stores/uiPhaseStore';

export function AvatarCompact() {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';

  const isSpeaking = mood === 'speaking';
  const isThinking = mood === 'thinking';
  const isExcited = mood === 'excited';

  return (
    <motion.div
      layoutId="avatar-main"
      className="relative flex items-center justify-center"
    >
      {/* Glow */}
      <motion.div
        className="absolute w-16 h-16 rounded-full blur-md"
        style={{
          background: isExcited
            ? 'radial-gradient(circle, rgba(45,212,191,0.3) 0%, transparent 70%)'
            : 'radial-gradient(circle, rgba(251,191,36,0.25) 0%, transparent 70%)'
        }}
        animate={{
          scale: isSpeaking ? [1, 1.3, 1] : [1, 1.1, 1],
          opacity: isSpeaking ? [0.5, 0.8, 0.5] : [0.3, 0.5, 0.3],
        }}
        transition={{ duration: isSpeaking ? 0.3 : 2, repeat: Infinity }}
      />

      {/* Main circle */}
      <motion.div
        className="relative w-12 h-12 rounded-full border-2 flex items-center justify-center overflow-hidden"
        style={{
          borderColor: isExcited ? 'rgba(45,212,191,0.6)' : 'rgba(251,191,36,0.4)',
          background: 'radial-gradient(circle at 30% 30%, rgba(30,41,59,0.95) 0%, rgba(15,23,42,0.98) 100%)',
          boxShadow: isExcited
            ? '0 0 20px rgba(45,212,191,0.3)'
            : '0 0 15px rgba(251,191,36,0.2)'
        }}
        animate={
          isExcited ? { scale: [1, 1.1, 1] } :
          isSpeaking ? { scale: [1, 1.03, 1] } :
          isThinking ? { rotate: [0, 5, -5, 0] } :
          {}
        }
        transition={{
          duration: isExcited ? 0.4 : isSpeaking ? 0.3 : 2,
          repeat: Infinity
        }}
      >
        {/* Grid overlay */}
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `
              linear-gradient(rgba(251,191,36,0.2) 1px, transparent 1px),
              linear-gradient(90deg, rgba(251,191,36,0.2) 1px, transparent 1px)
            `,
            backgroundSize: '8px 8px',
          }}
        />

        {/* Central core */}
        <motion.div
          className="relative w-5 h-5 rounded-full border border-amber-400/50 flex items-center justify-center"
          animate={isThinking ? { rotate: 360 } : {}}
          transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
        >
          <motion.div
            className="w-2.5 h-2.5 rounded-full"
            style={{
              background: isExcited
                ? 'radial-gradient(circle, #2dd4bf 0%, #0d9488 100%)'
                : 'radial-gradient(circle, #fbbf24 0%, #d97706 100%)',
              boxShadow: isExcited
                ? '0 0 10px rgba(45,212,191,0.8)'
                : '0 0 10px rgba(251,191,36,0.8)',
            }}
            animate={{
              scale: isSpeaking ? [1, 1.4, 1] : [1, 1.1, 1],
            }}
            transition={{
              duration: isSpeaking ? 0.3 : 1.5,
              repeat: Infinity,
            }}
          />
        </motion.div>

        {/* Mini waveform for speaking */}
        {isSpeaking && (
          <div className="absolute bottom-1 left-0 right-0 flex justify-center gap-px">
            {[1, 2, 3, 2, 1].map((h, i) => (
              <motion.div
                key={i}
                className="w-0.5 bg-amber-400 rounded-full"
                animate={{ height: [2, h * 2 + 2, 2] }}
                transition={{ duration: 0.2, repeat: Infinity, delay: i * 0.03 }}
              />
            ))}
          </div>
        )}
      </motion.div>

      {/* Thinking spinner */}
      {isThinking && (
        <motion.div
          className="absolute -top-1 -right-1 w-3 h-3 border border-amber-400 border-t-transparent rounded-full"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        />
      )}

      {/* Status dot */}
      <motion.div
        className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full border border-slate-800 ${
          isSpeaking ? 'bg-green-400' :
          isThinking ? 'bg-amber-400' :
          isExcited ? 'bg-teal-400' :
          'bg-slate-500'
        }`}
        animate={{
          scale: [1, 1.2, 1],
        }}
        transition={{ duration: 1, repeat: Infinity }}
      />
    </motion.div>
  );
}
