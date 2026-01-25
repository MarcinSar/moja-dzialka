import { useEffect, useMemo, useState, useRef } from 'react';
import { motion, useMotionValue, useSpring } from 'motion/react';
import { useUIPhaseStore, AvatarMood } from '../../stores/uiPhaseStore';
import { useChatStore } from '../../stores/chatStore';

// Shape types for morphing
type ShapeType = 'sphere' | 'ring' | 'helix' | 'wave' | 'burst';

// Generate points for different shapes
function generateShapePoints(
  shape: ShapeType,
  count: number,
  radius: number,
  time: number
): Array<{ x: number; y: number; z: number }> {
  const points = [];
  const phi = Math.PI * (3 - Math.sqrt(5)); // Golden angle

  for (let i = 0; i < count; i++) {
    const t = i / (count - 1);
    let x = 0, y = 0, z = 0;

    switch (shape) {
      case 'sphere': {
        const yPos = 1 - t * 2;
        const radiusAtY = Math.sqrt(1 - yPos * yPos);
        const theta = phi * i;
        x = Math.cos(theta) * radiusAtY * radius;
        y = yPos * radius;
        z = Math.sin(theta) * radiusAtY * radius;
        break;
      }
      case 'ring': {
        const angle = (i / count) * Math.PI * 2;
        const ringRadius = radius * 0.8;
        x = Math.cos(angle) * ringRadius;
        y = Math.sin(angle * 3 + time * 0.5) * 15;
        z = Math.sin(angle) * ringRadius;
        break;
      }
      case 'helix': {
        const helixAngle = (i / count) * Math.PI * 4;
        const helixRadius = radius * 0.5;
        x = Math.cos(helixAngle) * helixRadius;
        y = (t - 0.5) * radius * 2;
        z = Math.sin(helixAngle) * helixRadius;
        break;
      }
      case 'wave': {
        const waveX = (t - 0.5) * radius * 2;
        const waveY = Math.sin(t * Math.PI * 3 + time * 0.8) * radius * 0.4;
        const waveZ = Math.cos(t * Math.PI * 2) * radius * 0.3;
        x = waveX;
        y = waveY;
        z = waveZ;
        break;
      }
      case 'burst': {
        const burstAngle = phi * i;
        const burstY = 1 - t * 2;
        const burstRadius = Math.sqrt(1 - burstY * burstY) * radius * (1 + Math.sin(time * 1.5 + i * 0.1) * 0.2);
        x = Math.cos(burstAngle) * burstRadius;
        y = burstY * radius;
        z = Math.sin(burstAngle) * burstRadius;
        break;
      }
    }

    points.push({ x, y, z });
  }
  return points;
}

// Smooth easing function
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// Orbiting particle system - uses refs to avoid resets
function OrbitingParticles({
  primaryColor,
  moodIntensity
}: {
  primaryColor: string;
  moodIntensity: number;
}) {
  const timeRef = useRef(0);
  const [, forceUpdate] = useState(0);
  const particleCount = 20;

  useEffect(() => {
    let animationId: number;
    const animate = () => {
      timeRef.current += 0.004; // Very slow
      forceUpdate(n => n + 1);
      animationId = requestAnimationFrame(animate);
    };
    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, []);

  const time = timeRef.current;

  return (
    <svg className="absolute inset-0 w-full h-full overflow-visible" viewBox="-150 -150 300 300">
      {Array.from({ length: particleCount }).map((_, i) => {
        const baseAngle = (i / particleCount) * Math.PI * 2;
        const orbitRadius = 85 + (i % 3) * 18;
        const orbitSpeed = 0.15 + (i % 4) * 0.05; // Slower orbits
        const verticalOffset = Math.sin(i * 1.5) * 25;
        const tiltX = Math.sin(i * 0.7) * 0.25;

        const angle = baseAngle + time * orbitSpeed;
        const x = Math.cos(angle) * orbitRadius;
        const baseY = Math.sin(angle) * orbitRadius * tiltX + verticalOffset;
        const z = Math.sin(angle) * orbitRadius;

        const waveAmplitude = moodIntensity * 12;
        const y = baseY + Math.sin(time * 0.8 + i * 0.3) * waveAmplitude;

        const scale = 200 / (200 + z);
        const projX = x * scale;
        const projY = y * scale;

        const size = (1.5 + (i % 3) + moodIntensity * 1.5) * scale;
        const opacity = 0.2 + moodIntensity * 0.3 + Math.sin(time * 0.5 + i * 0.2) * 0.1;

        return (
          <g key={i}>
            <line
              x1={0}
              y1={0}
              x2={projX}
              y2={projY}
              stroke={primaryColor}
              strokeWidth={0.2}
              opacity={opacity * 0.15}
            />
            <circle
              cx={projX}
              cy={projY}
              r={size}
              fill={i % 5 === 0 ? '#fff' : primaryColor}
              opacity={opacity}
            />
          </g>
        );
      })}
    </svg>
  );
}

// Main Point Cloud Entity - persistent animation state
function PointCloudEntity({
  mood,
  moodIntensity,
  targetShape,
  morphProgress,
  currentShapeRef
}: {
  mood: AvatarMood;
  moodIntensity: number;
  targetShape: ShapeType;
  morphProgress: number;
  currentShapeRef: React.MutableRefObject<ShapeType>;
}) {
  // Persistent animation state in refs - never resets
  const timeRef = useRef(0);
  const rotationRef = useRef(0);
  const [, forceUpdate] = useState(0);

  const pointCount = 50;
  const radius = 50;

  // Continuous animation loop - constant speed, no mood dependency
  useEffect(() => {
    let animationId: number;
    let lastTime = Date.now();

    const animate = () => {
      const now = Date.now();
      const delta = (now - lastTime) / 1000;
      lastTime = now;

      // Constant slow progression
      timeRef.current += delta * 0.3;

      // Constant slow rotation
      rotationRef.current += delta * 0.04;

      forceUpdate(n => n + 1);
      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, []);

  const time = timeRef.current;
  const rotationY = rotationRef.current;

  // Generate and interpolate points with smooth morphing
  const projectedPoints = useMemo(() => {
    const currentShape = currentShapeRef.current;
    const fromPoints = generateShapePoints(currentShape, pointCount, radius, time);
    const toPoints = generateShapePoints(targetShape, pointCount, radius, time);

    // Smooth easing for morph
    const easedProgress = easeInOutCubic(morphProgress);

    const cosY = Math.cos(rotationY);
    const sinY = Math.sin(rotationY);

    return fromPoints.map((from, i) => {
      const to = toPoints[i];

      // Interpolate position
      const px = from.x + (to.x - from.x) * easedProgress;
      const py = from.y + (to.y - from.y) * easedProgress;
      const pz = from.z + (to.z - from.z) * easedProgress;

      // Add subtle organic movement
      const breathe = Math.sin(time * 0.4 + i * 0.12) * (3 + moodIntensity * 5);

      // Rotate around Y axis
      const x = (px + Math.sin(time * 0.5 + i * 0.08) * breathe * 0.08) * cosY - pz * sinY;
      const z = px * sinY + pz * cosY;
      const y = py + Math.cos(time * 0.35 + i * 0.08) * breathe * 0.08;

      // Perspective projection
      const scale = 200 / (200 + z);
      const projX = x * scale + 100;
      const projY = y * scale + 100;

      return {
        x: projX,
        y: projY,
        z,
        scale,
        opacity: Math.max(0.25, Math.min(1, (z + radius) / (radius * 2))),
      };
    });
  }, [time, rotationY, targetShape, morphProgress, currentShapeRef, moodIntensity, pointCount, radius]);

  // Generate connections
  const connections = useMemo(() => {
    const conns: Array<{ from: number; to: number }> = [];
    const maxDist = 40 + moodIntensity * 15;

    for (let i = 0; i < projectedPoints.length; i++) {
      for (let j = i + 1; j < projectedPoints.length; j++) {
        const dx = projectedPoints[i].x - projectedPoints[j].x;
        const dy = projectedPoints[i].y - projectedPoints[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < maxDist) {
          conns.push({ from: i, to: j });
        }
      }
    }
    return conns;
  }, [projectedPoints, moodIntensity]);

  // Smoothly interpolated colors
  const primaryColor = mood === 'excited' ? '#a78bfa' :
                       mood === 'thinking' ? '#60a5fa' :
                       mood === 'speaking' ? '#22d3ee' : '#38bdf8';
  const secondaryColor = mood === 'excited' ? '#7c3aed' :
                         mood === 'thinking' ? '#2563eb' :
                         mood === 'speaking' ? '#06b6d4' : '#0ea5e9';

  return (
    <div className="relative w-[200px] h-[200px]">
      <svg viewBox="0 0 200 200" className="w-full h-full overflow-visible">
        <defs>
          <radialGradient id="coreGlow3" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={primaryColor} stopOpacity="0.9" />
            <stop offset="50%" stopColor={secondaryColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={secondaryColor} stopOpacity="0" />
          </radialGradient>
          <filter id="glow3" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Core glow */}
        <circle
          cx="100"
          cy="100"
          r={22 + moodIntensity * 8 + Math.sin(time * 0.5) * 3}
          fill="url(#coreGlow3)"
          opacity={0.4 + moodIntensity * 0.25}
        />

        {/* Connection lines */}
        <g>
          {connections.map((conn, i) => {
            const from = projectedPoints[conn.from];
            const to = projectedPoints[conn.to];
            const avgOpacity = (from.opacity + to.opacity) / 2;
            const pulseOpacity = 0.08 + Math.sin(time * 0.6 + i * 0.03) * 0.08 + moodIntensity * 0.15;

            return (
              <line
                key={`conn-${i}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={primaryColor}
                strokeWidth={0.4 + moodIntensity * 0.3}
                opacity={avgOpacity * pulseOpacity}
              />
            );
          })}
        </g>

        {/* Points */}
        {projectedPoints.map((point, i) => {
          const baseSize = 1.2 + point.scale * 1.2;
          const pulseSize = baseSize * (1 + Math.sin(time * 0.6 + i * 0.08) * 0.12 * moodIntensity);

          return (
            <circle
              key={`point-${i}`}
              cx={point.x}
              cy={point.y}
              r={pulseSize}
              fill={i % 7 === 0 ? '#fff' : primaryColor}
              opacity={point.opacity * (0.4 + moodIntensity * 0.35)}
              filter={i % 7 === 0 ? 'url(#glow3)' : undefined}
            />
          );
        })}

        {/* Central core */}
        <circle
          cx="100"
          cy="100"
          r={5 + moodIntensity * 3 + Math.sin(time * 0.7) * 1.5}
          fill={primaryColor}
          filter="url(#glow3)"
          opacity={0.85}
        />

        {/* Inner highlight */}
        <circle
          cx="98"
          cy="98"
          r="1.5"
          fill="#fff"
          opacity={0.65}
        />
      </svg>
    </div>
  );
}

// Main exported component
export function AvatarFull() {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';
  const messages = useChatStore((s) => s.messages);
  const hasMessages = messages.length > 0;

  // Refs for persistent state that shouldn't reset
  const currentShapeRef = useRef<ShapeType>('sphere');
  const morphProgressRef = useRef(0);
  const lastMoodRef = useRef<AvatarMood>(mood);
  const positionPhaseRef = useRef(0);
  const lastPositionChangeRef = useRef(Date.now());

  // Morph progress as motion value for smooth interpolation
  const morphProgressMotion = useMotionValue(0);
  const smoothMorphProgress = useSpring(morphProgressMotion, {
    damping: 15,
    stiffness: 20,
    mass: 1.5
  });

  // Mood intensity with very slow spring
  const rawMoodIntensity = mood === 'idle' ? 0.1 : mood === 'thinking' ? 0.5 : mood === 'speaking' ? 0.7 : 0.9;
  const moodIntensityMotion = useMotionValue(rawMoodIntensity);
  const moodIntensity = useSpring(moodIntensityMotion, {
    damping: 12,
    stiffness: 15,
    mass: 2
  });

  // Position with springs for smooth but noticeable movement
  const posX = useMotionValue(0);
  const posY = useMotionValue(0);
  const springX = useSpring(posX, { damping: 20, stiffness: 15, mass: 2 });
  const springY = useSpring(posY, { damping: 20, stiffness: 15, mass: 2 });

  // Target shape based on mood
  const targetShape: ShapeType = useMemo(() => {
    switch (mood) {
      case 'thinking': return 'helix';
      case 'speaking': return 'wave';
      case 'excited': return 'burst';
      default: return 'sphere';
    }
  }, [mood]);

  // Handle mood changes - start morph transition
  useEffect(() => {
    if (mood !== lastMoodRef.current) {
      // Mood changed - start morphing to new shape
      lastMoodRef.current = mood;
      currentShapeRef.current = targetShape === 'sphere' ?
        (morphProgressRef.current > 0.5 ? currentShapeRef.current : 'sphere') :
        currentShapeRef.current;
      morphProgressRef.current = 0;
      morphProgressMotion.set(0);
    }
    moodIntensityMotion.set(rawMoodIntensity);
  }, [mood, rawMoodIntensity, moodIntensityMotion, targetShape, morphProgressMotion]);

  // Continuous morph animation
  useEffect(() => {
    let animationId: number;

    const animate = () => {
      // Very slow morph progression
      if (morphProgressRef.current < 1) {
        morphProgressRef.current = Math.min(1, morphProgressRef.current + 0.003);
        morphProgressMotion.set(morphProgressRef.current);
      } else if (currentShapeRef.current !== targetShape) {
        // Morph complete, update current shape
        currentShapeRef.current = targetShape;
      }

      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, [targetShape, morphProgressMotion]);

  // Position movement - noticeable wandering and floating
  useEffect(() => {
    let animationId: number;

    const updatePosition = () => {
      const now = Date.now();
      const elapsed = (now - lastPositionChangeRef.current) / 1000;

      // Change position target every 6-12 seconds
      if (elapsed > 6 + Math.random() * 6) {
        positionPhaseRef.current = (positionPhaseRef.current + 1) % 8;
        lastPositionChangeRef.current = now;
      }

      // Much larger movement range
      const moveRange = hasMessages ? 60 : 100;
      const phase = positionPhaseRef.current;

      // More positions for variety
      const positions = [
        { x: 0, y: 0 },
        { x: moveRange * 0.8, y: -moveRange * 0.4 },
        { x: -moveRange * 0.6, y: moveRange * 0.5 },
        { x: moveRange * 0.4, y: moveRange * 0.6 },
        { x: -moveRange * 0.9, y: -moveRange * 0.3 },
        { x: moveRange * 0.5, y: -moveRange * 0.7 },
        { x: -moveRange * 0.3, y: moveRange * 0.8 },
        { x: moveRange * 0.7, y: moveRange * 0.2 },
      ];

      const target = positions[phase];

      // Strong floating motion overlay
      const time = now / 1000;
      const floatX = Math.sin(time * 0.25) * 25 + Math.sin(time * 0.13) * 15 + Math.sin(time * 0.07) * 8;
      const floatY = Math.cos(time * 0.2) * 20 + Math.cos(time * 0.11) * 12 + Math.cos(time * 0.05) * 6;

      posX.set(target.x + floatX);
      posY.set(target.y + floatY);

      animationId = requestAnimationFrame(updatePosition);
    };

    animationId = requestAnimationFrame(updatePosition);
    return () => cancelAnimationFrame(animationId);
  }, [posX, posY, hasMessages]);

  // Subscribe to spring values for child components
  const [currentMorphProgress, setCurrentMorphProgress] = useState(0);
  const [currentIntensity, setCurrentIntensity] = useState(0.1);

  useEffect(() => {
    const unsubMorph = smoothMorphProgress.on('change', setCurrentMorphProgress);
    const unsubIntensity = moodIntensity.on('change', setCurrentIntensity);
    return () => {
      unsubMorph();
      unsubIntensity();
    };
  }, [smoothMorphProgress, moodIntensity]);

  // Colors
  const primaryColor = mood === 'excited' ? '#a78bfa' :
                       mood === 'speaking' ? '#22d3ee' :
                       mood === 'thinking' ? '#60a5fa' : '#38bdf8';

  const statusColor = primaryColor;
  const statusText = mood === 'speaking' ? 'TRANSMITTING' :
                     mood === 'thinking' ? 'PROCESSING' :
                     mood === 'excited' ? 'READY' :
                     'LISTENING';

  return (
    <motion.div
      layoutId="avatar-main"
      className="relative flex flex-col items-center"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 1.5, ease: [0.22, 1, 0.36, 1] }}
      style={{ x: springX, y: springY }}
    >
      {/* Ambient glow - constant slow animation, no mood dependency */}
      <motion.div
        className="absolute inset-[-60%] rounded-full blur-3xl pointer-events-none"
        style={{
          background: `radial-gradient(circle, ${statusColor}20 0%, transparent 70%)`,
        }}
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.25, 0.4, 0.25],
        }}
        transition={{
          duration: 6,
          repeat: Infinity,
          ease: "easeInOut"
        }}
      />

      {/* Orbiting particles */}
      <div className="absolute inset-[-50px] pointer-events-none">
        <OrbitingParticles primaryColor={primaryColor} moodIntensity={currentIntensity} />
      </div>

      {/* Main point cloud entity */}
      <PointCloudEntity
        mood={mood}
        moodIntensity={currentIntensity}
        targetShape={targetShape}
        morphProgress={currentMorphProgress}
        currentShapeRef={currentShapeRef}
      />

      {/* Status indicator - constant animation */}
      <motion.div
        className="mt-6 text-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 1 }}
      >
        <motion.div className="flex items-center justify-center gap-2">
          <motion.span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: statusColor }}
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.5, 0.8, 0.5],
            }}
            transition={{
              duration: 2.5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
          <motion.span
            className="text-xs font-mono tracking-widest uppercase"
            style={{ color: statusColor }}
            animate={{ opacity: [0.5, 0.75, 0.5] }}
            transition={{ duration: 4, repeat: Infinity }}
          >
            {statusText}
          </motion.span>
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
