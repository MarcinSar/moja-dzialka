import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { motion, useAnimation, useMotionValue, useTransform, useSpring } from 'motion/react';
import { useUIPhaseStore, AvatarMood } from '../../stores/uiPhaseStore';

// Organic blob shape generator with time-based morphing
function generateBlobPath(complexity: number, variance: number, phase: number, time: number = 0): string {
  const points: string[] = [];
  const angleStep = (Math.PI * 2) / complexity;

  for (let i = 0; i < complexity; i++) {
    const angle = i * angleStep + phase;
    // Add time-based wobble for continuous morphing
    const wobble = Math.sin(time * 0.002 + i * 0.5) * 8 + Math.cos(time * 0.003 + i * 0.7) * 5;
    const radius = 80 + Math.sin(angle * 3 + phase + time * 0.001) * variance + Math.cos(angle * 2) * (variance * 0.5) + wobble;
    const x = 100 + Math.cos(angle) * radius;
    const y = 100 + Math.sin(angle) * radius;
    points.push(`${x},${y}`);
  }

  // Create smooth curve through points
  let path = `M ${points[0]}`;
  for (let i = 0; i < points.length; i++) {
    const p0 = points[(i - 1 + points.length) % points.length].split(',').map(Number);
    const p1 = points[i].split(',').map(Number);
    const p2 = points[(i + 1) % points.length].split(',').map(Number);
    const p3 = points[(i + 2) % points.length].split(',').map(Number);

    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;

    path += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2[0]},${p2[1]}`;
  }

  return path + ' Z';
}

// Flowing particles that orbit around
function FlowingParticles({ mood = 'idle', count = 24 }: { mood: AvatarMood; count?: number }) {
  const isActive = mood !== 'idle';
  const isExcited = mood === 'excited';

  return (
    <div className="absolute inset-0 pointer-events-none">
      {Array.from({ length: count }).map((_, i) => {
        const angle = (i / count) * Math.PI * 2;
        const distance = 160 + (i % 3) * 35;
        const size = 2 + (i % 4);
        const delay = i * 0.1;

        return (
          <motion.div
            key={i}
            className={`absolute rounded-full ${
              i % 3 === 0 ? 'bg-cyan-400' :
              i % 3 === 1 ? 'bg-blue-400' : 'bg-white/70'
            }`}
            style={{
              width: size,
              height: size,
              left: '50%',
              top: '50%',
            }}
            animate={isActive ? {
              x: [
                Math.cos(angle) * distance,
                Math.cos(angle + 0.5) * (distance + (isExcited ? 40 : 20)),
                Math.cos(angle + 1) * distance,
                Math.cos(angle) * distance,
              ],
              y: [
                Math.sin(angle) * distance,
                Math.sin(angle + 0.5) * (distance + (isExcited ? 40 : 20)),
                Math.sin(angle + 1) * distance,
                Math.sin(angle) * distance,
              ],
              opacity: [0.2, 0.8, 0.2],
              scale: isExcited ? [1, 2, 1] : [1, 1.3, 1],
            } : {
              x: Math.cos(angle) * distance * 0.8,
              y: Math.sin(angle) * distance * 0.8,
              opacity: 0.15,
              scale: 1,
            }}
            transition={{
              duration: isExcited ? 1.5 : 4,
              repeat: Infinity,
              delay,
              ease: "easeInOut",
            }}
          />
        );
      })}
    </div>
  );
}

// Audio visualization waves
function AudioWaves({ isActive }: { isActive: boolean }) {
  const waveCount = 4;

  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      {Array.from({ length: waveCount }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full border border-cyan-400/30"
          style={{
            width: 200 + i * 50,
            height: 200 + i * 50,
          }}
          animate={isActive ? {
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.1, 0.3],
          } : {
            scale: 1,
            opacity: 0.1,
          }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            delay: i * 0.2,
            ease: "easeOut",
          }}
        />
      ))}
    </div>
  );
}

// Main organic blob with mouse interaction
function OrganicBlob({ mood = 'idle' }: { mood: AvatarMood }) {
  const blobControls = useAnimation();
  const coreControls = useAnimation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [time, setTime] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  // Mouse position for interaction
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Smooth spring values for blob distortion
  const springConfig = { damping: 25, stiffness: 200 };
  const blobX = useSpring(mouseX, springConfig);
  const blobY = useSpring(mouseY, springConfig);

  // Transform mouse position to rotation
  const rotateX = useTransform(blobY, [-50, 50], [10, -10]);
  const rotateY = useTransform(blobX, [-50, 50], [-10, 10]);

  const isSpeaking = mood === 'speaking';
  const isThinking = mood === 'thinking';
  const isExcited = mood === 'excited';

  // Continuous morphing animation
  useEffect(() => {
    let animationId: number;
    const animate = () => {
      setTime(Date.now());
      animationId = requestAnimationFrame(animate);
    };
    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, []);

  // Mouse move handler
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    mouseX.set((e.clientX - centerX) * 0.3);
    mouseY.set((e.clientY - centerY) * 0.3);
  }, [mouseX, mouseY]);

  const handleMouseLeave = useCallback(() => {
    mouseX.set(0);
    mouseY.set(0);
    setIsHovered(false);
  }, [mouseX, mouseY]);

  // Generate current blob path with time-based morphing
  const complexity = isExcited ? 6 : isThinking ? 12 : isSpeaking ? 10 : 8;
  const variance = isExcited ? 35 : isThinking ? 25 : isSpeaking ? 28 : 18;
  const phase = isExcited ? Math.PI : isThinking ? Math.PI / 4 : isSpeaking ? Math.PI / 2 : 0;
  const currentPath = useMemo(() =>
    generateBlobPath(complexity, variance + (isHovered ? 8 : 0), phase, time),
    [complexity, variance, phase, time, isHovered]
  );

  useEffect(() => {
    if (isThinking) {
      blobControls.start({
        rotate: [0, 360],
        scale: [1, 1.05, 0.95, 1],
        transition: { rotate: { duration: 8, repeat: Infinity, ease: "linear" }, scale: { duration: 2, repeat: Infinity } }
      });
      coreControls.start({
        scale: [1, 0.8, 1],
        opacity: [0.8, 1, 0.8],
        transition: { duration: 1.5, repeat: Infinity }
      });
    } else if (isSpeaking) {
      blobControls.start({
        scale: [1, 1.08, 0.95, 1.05, 1],
        rotate: 0,
        transition: { duration: 0.6, repeat: Infinity }
      });
      coreControls.start({
        scale: [1, 1.4, 1],
        opacity: 1,
        transition: { duration: 0.25, repeat: Infinity }
      });
    } else if (isExcited) {
      blobControls.start({
        scale: [1, 1.15, 1],
        rotate: [0, 10, -10, 0],
        transition: { duration: 0.8, repeat: Infinity }
      });
      coreControls.start({
        scale: [1, 1.5, 1],
        opacity: 1,
        transition: { duration: 0.5, repeat: Infinity }
      });
    } else {
      blobControls.start({
        scale: 1,
        rotate: 0,
        transition: { duration: 1 }
      });
      coreControls.start({
        scale: 1,
        opacity: 0.7,
        transition: { duration: 1 }
      });
    }
  }, [mood, blobControls, coreControls, isSpeaking, isThinking, isExcited]);

  // Blue/cyan palette - modern AI aesthetic
  const gradientColors = isExcited
    ? ['#a78bfa', '#7c3aed']  // violet when excited
    : isThinking
    ? ['#60a5fa', '#2563eb']  // blue when thinking
    : isSpeaking
    ? ['#22d3ee', '#06b6d4']  // cyan when speaking
    : ['#38bdf8', '#0ea5e9']; // sky blue idle

  const glowColor = isExcited ? 'rgba(167,139,250,0.5)' :
                    isSpeaking ? 'rgba(34,211,238,0.5)' :
                    isThinking ? 'rgba(96,165,250,0.4)' :
                    'rgba(56,189,248,0.35)';

  return (
    <motion.div
      ref={containerRef}
      className="relative w-[280px] h-[280px] cursor-pointer"
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      animate={{ y: [0, -12, 0] }}
      transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      style={{
        perspective: 800,
      }}
    >
      {/* Glow effect - larger and more dynamic */}
      <motion.div
        className="absolute inset-[-20%] blur-3xl"
        style={{
          background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
        }}
        animate={{
          scale: isSpeaking ? [1, 1.4, 1] : isHovered ? [1, 1.2, 1] : [1, 1.15, 1],
          opacity: isSpeaking ? [0.6, 1, 0.6] : [0.5, 0.8, 0.5],
        }}
        transition={{ duration: isSpeaking ? 0.4 : 2, repeat: Infinity }}
      />

      {/* Main blob SVG with 3D rotation on hover */}
      <motion.svg
        viewBox="0 0 200 200"
        className="w-full h-full"
        animate={blobControls}
        style={{
          rotateX,
          rotateY,
          transformStyle: 'preserve-3d',
        }}
      >
        <defs>
          <linearGradient id="blobGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <motion.stop
              offset="0%"
              stopOpacity="0.9"
              animate={{ stopColor: gradientColors[0] }}
              transition={{ duration: 0.5 }}
            />
            <motion.stop
              offset="100%"
              stopOpacity="0.7"
              animate={{ stopColor: gradientColors[1] }}
              transition={{ duration: 0.5 }}
            />
          </linearGradient>
          <radialGradient id="coreGradient" cx="30%" cy="30%">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.8" />
            <stop offset="50%" stopColor={gradientColors[0]} stopOpacity="0.9" />
            <stop offset="100%" stopColor={gradientColors[1]} stopOpacity="1" />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="innerGlow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Outer glow ring */}
        <motion.circle
          cx="100"
          cy="100"
          fill="none"
          stroke={gradientColors[0]}
          strokeWidth="0.5"
          strokeOpacity={isHovered ? 0.4 : 0.2}
          initial={{ r: 95 }}
          animate={{
            r: isHovered ? [95, 98, 95] : 95,
          }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />

        {/* Main blob shape - continuously morphing */}
        <motion.path
          d={currentPath}
          fill="url(#blobGradient)"
          filter="url(#glow)"
          style={{
            transformOrigin: 'center',
          }}
        />

        {/* Inner highlight blob */}
        <motion.ellipse
          cx="85"
          cy="85"
          fill="white"
          fillOpacity={0.15}
          initial={{ rx: 25, ry: 20 }}
          animate={{
            rx: [25, 28, 25],
            ry: [20, 22, 20],
          }}
          transition={{ duration: 3, repeat: Infinity }}
        />

        {/* Inner structure ring */}
        <motion.circle
          cx="100"
          cy="100"
          fill="none"
          stroke={gradientColors[0]}
          strokeWidth="1.5"
          strokeOpacity={0.3}
          strokeDasharray="8 4"
          initial={{ r: 50 }}
          animate={{
            rotate: isThinking ? 360 : isHovered ? 180 : 0,
            r: isSpeaking ? [50, 55, 50] : 50,
          }}
          transition={{
            rotate: { duration: isThinking ? 4 : 20, repeat: Infinity, ease: "linear" },
            r: { duration: 0.3, repeat: Infinity }
          }}
          style={{ transformOrigin: 'center' }}
        />

        {/* Secondary inner ring */}
        <motion.circle
          cx="100"
          cy="100"
          r="35"
          fill="none"
          stroke={gradientColors[1]}
          strokeWidth="1"
          strokeOpacity={0.2}
          strokeDasharray="4 6"
          animate={{
            rotate: isThinking ? -360 : isHovered ? -90 : 0,
          }}
          transition={{
            rotate: { duration: isThinking ? 6 : 30, repeat: Infinity, ease: "linear" },
          }}
          style={{ transformOrigin: 'center' }}
        />

        {/* Core - pulsing center */}
        <motion.circle
          cx="100"
          cy="100"
          r={isSpeaking ? 24 : 20}
          fill="url(#coreGradient)"
          filter="url(#innerGlow)"
          animate={coreControls}
          style={{
            filter: `drop-shadow(0 0 ${isSpeaking ? '25px' : isHovered ? '18px' : '12px'} ${gradientColors[0]})`,
          }}
        />

        {/* Core inner highlight */}
        <motion.circle
          cx="94"
          cy="94"
          r="8"
          fill="white"
          fillOpacity={0.4}
          animate={{
            fillOpacity: isSpeaking ? [0.4, 0.7, 0.4] : [0.3, 0.5, 0.3],
          }}
          transition={{ duration: isSpeaking ? 0.3 : 2, repeat: Infinity }}
        />
      </motion.svg>

      {/* Audio waves when speaking - larger */}
      {isSpeaking && <AudioWaves isActive={true} />}

      {/* Processing indicator when thinking */}
      {isThinking && (
        <motion.div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 border-2 border-blue-400/50 rounded-full border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
      )}

      {/* Hover ripple effect */}
      {isHovered && (
        <motion.div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/30"
          initial={{ width: 100, height: 100, opacity: 0.5 }}
          animate={{
            width: [100, 300],
            height: [100, 300],
            opacity: [0.5, 0],
          }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}
    </motion.div>
  );
}

export function AvatarFull() {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';

  return (
    <motion.div
      layoutId="avatar-main"
      className="relative flex flex-col items-center"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
    >
      {/* Flowing particles */}
      <FlowingParticles mood={mood} />

      {/* Main organic blob */}
      <OrganicBlob mood={mood} />

      {/* Status text - minimal */}
      <motion.div
        className="mt-4 text-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        <motion.span
          className="text-xs font-mono tracking-widest uppercase"
          style={{
            color: mood === 'excited' ? '#a78bfa' :
                   mood === 'speaking' ? '#22d3ee' :
                   mood === 'thinking' ? '#60a5fa' :
                   '#64748b'
          }}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          {mood === 'speaking' ? '● TRANSMITTING' :
           mood === 'thinking' ? '◐ PROCESSING' :
           mood === 'excited' ? '★ READY' :
           '○ LISTENING'}
        </motion.span>
      </motion.div>
    </motion.div>
  );
}
