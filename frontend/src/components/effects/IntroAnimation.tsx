import { useState, useEffect } from 'react';
import { motion } from 'motion/react';

interface IntroAnimationProps {
  onStartExit: () => void;  // Called when exit starts (avatar can start growing)
  onComplete: () => void;   // Called when fully done
}

const introLines = [
  { text: "Cześć!", delay: 0 },
  { text: "Jestem Parcela", delay: 0.8 },
  { text: "i pomogę Ci znaleźć wymarzoną działkę.", delay: 1.8 },
  { text: "Opowiedz mi czego szukasz...", delay: 3.2 },
];

export function IntroAnimation({ onStartExit, onComplete }: IntroAnimationProps) {
  const [currentLine, setCurrentLine] = useState(0);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    // Progress through lines
    introLines.forEach((line, index) => {
      if (index > 0) {
        const timer = setTimeout(() => {
          setCurrentLine(index);
        }, line.delay * 1000);
        timers.push(timer);
      }
    });

    // Start exit animation - notify parent so avatar can start growing
    const exitTimer = setTimeout(() => {
      setIsExiting(true);
      onStartExit();
    }, 4500);
    timers.push(exitTimer);

    // Complete after exit animation
    const completeTimer = setTimeout(() => {
      onComplete();
    }, 5500);
    timers.push(completeTimer);

    return () => timers.forEach(t => clearTimeout(t));
  }, [onStartExit, onComplete]);

  return (
    <motion.div
      className="absolute inset-0 flex flex-col items-center justify-center z-30 pointer-events-none"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Text container - positioned above center to leave room for avatar */}
      <motion.div
        className="text-center max-w-xl px-6 mb-8"
        animate={isExiting ? {
          opacity: 0,
          y: -60,
          scale: 0.9,
          filter: 'blur(10px)',
        } : {
          opacity: 1,
          y: 0,
          scale: 1,
          filter: 'blur(0px)',
        }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      >
        {/* Greeting with wave emoji */}
        {currentLine >= 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="mb-4"
          >
            <motion.span
              className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-amber-400 via-amber-300 to-teal-400 bg-clip-text text-transparent"
              animate={{
                backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
              }}
              transition={{ duration: 3, repeat: Infinity }}
              style={{ backgroundSize: '200% 200%' }}
            >
              {introLines[0].text}
            </motion.span>
            <motion.span
              className="inline-block ml-3 text-4xl"
              animate={{ rotate: [0, 14, -8, 14, 0] }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
              👋
            </motion.span>
          </motion.div>
        )}

        {/* Name introduction */}
        {currentLine >= 1 && (
          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-xl md:text-2xl text-white mb-2"
          >
            <span className="text-slate-400">Jestem </span>
            <motion.span
              className="font-semibold text-teal-400"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              Parcela
            </motion.span>
          </motion.p>
        )}

        {/* Purpose line */}
        {currentLine >= 2 && (
          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-lg md:text-xl text-slate-300 mb-6"
          >
            i pomogę Ci znaleźć{' '}
            <span className="text-amber-400 font-medium">wymarzoną działkę</span>.
          </motion.p>
        )}

        {/* Call to action */}
        {currentLine >= 3 && (
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <p className="text-slate-400 text-base md:text-lg">
              Opowiedz mi czego szukasz...
            </p>
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  );
}
