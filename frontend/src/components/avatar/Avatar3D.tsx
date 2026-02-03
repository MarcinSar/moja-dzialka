/**
 * Avatar3D - Three.js based 3D avatar with reactive animations
 *
 * This component creates a sophisticated 3D entity that responds to
 * different moods (idle, thinking, speaking, excited).
 *
 * Future enhancements:
 * - Load GLB models from Ready Player Me or custom models
 * - Add Mixamo animations
 * - Integrate lip-sync with Web Speech API
 * - Add facial morph targets for expressions
 */
import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Float, MeshDistortMaterial, Sparkles, Trail } from '@react-three/drei';
import * as THREE from 'three';
import { useUIPhaseStore, AvatarMood } from '@/stores/uiPhaseStore';

// Mood to color mapping
const MOOD_COLORS: Record<AvatarMood, { primary: string; secondary: string; emissive: string }> = {
  idle: { primary: '#38bdf8', secondary: '#0ea5e9', emissive: '#0284c7' },
  thinking: { primary: '#60a5fa', secondary: '#2563eb', emissive: '#1d4ed8' },
  speaking: { primary: '#22d3ee', secondary: '#06b6d4', emissive: '#0891b2' },
  excited: { primary: '#a78bfa', secondary: '#7c3aed', emissive: '#6d28d9' },
};

// Core entity - the main 3D shape
function CoreEntity({ mood, moodIntensity }: { mood: AvatarMood; moodIntensity: number }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const colors = MOOD_COLORS[mood];

  // Animate distortion based on mood
  useFrame((state) => {
    if (meshRef.current) {
      // Subtle rotation
      meshRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.3) * 0.1;
      meshRef.current.rotation.x = Math.cos(state.clock.elapsedTime * 0.2) * 0.05;

      // Pulsing scale based on mood
      const pulse = mood === 'speaking'
        ? 1 + Math.sin(state.clock.elapsedTime * 8) * 0.03 * moodIntensity
        : 1 + Math.sin(state.clock.elapsedTime * 2) * 0.02;
      meshRef.current.scale.setScalar(pulse);
    }
  });

  return (
    <Float
      speed={mood === 'thinking' ? 2 : 1.5}
      rotationIntensity={mood === 'excited' ? 0.5 : 0.2}
      floatIntensity={mood === 'speaking' ? 1.5 : 1}
    >
      <mesh ref={meshRef} castShadow>
        <icosahedronGeometry args={[1, 4]} />
        <MeshDistortMaterial
          color={colors.primary}
          emissive={colors.emissive}
          emissiveIntensity={0.3 + moodIntensity * 0.4}
          metalness={0.3}
          roughness={0.4}
          distort={0.3 + moodIntensity * 0.2}
          speed={mood === 'speaking' ? 4 : 2}
        />
      </mesh>
    </Float>
  );
}

// Orbiting particles
function OrbitingRing({
  radius,
  count,
  size,
  color,
  speed,
  yOffset = 0,
}: {
  radius: number;
  count: number;
  size: number;
  color: string;
  speed: number;
  yOffset?: number;
}) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * speed;
      groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.5) * 0.1;
    }
  });

  const particles = useMemo(() => {
    const temp = [];
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      temp.push({ x, y: yOffset, z, scale: 0.5 + Math.random() * 0.5 });
    }
    return temp;
  }, [count, radius, yOffset]);

  return (
    <group ref={groupRef}>
      {particles.map((p, i) => (
        <mesh key={i} position={[p.x, p.y, p.z]} scale={p.scale}>
          <sphereGeometry args={[size, 8, 8]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.5}
            transparent
            opacity={0.8}
          />
        </mesh>
      ))}
    </group>
  );
}

// Energy trails
function EnergyTrail({ mood }: { mood: AvatarMood }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const colors = MOOD_COLORS[mood];

  useFrame((state) => {
    if (meshRef.current) {
      const t = state.clock.elapsedTime;
      meshRef.current.position.x = Math.sin(t * 2) * 1.5;
      meshRef.current.position.y = Math.cos(t * 1.5) * 0.8;
      meshRef.current.position.z = Math.sin(t * 1.8) * 1.2;
    }
  });

  return (
    <Trail
      width={0.3}
      length={6}
      color={new THREE.Color(colors.secondary)}
      attenuation={(t) => t * t}
    >
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial
          color={colors.primary}
          emissive={colors.emissive}
          emissiveIntensity={1}
        />
      </mesh>
    </Trail>
  );
}

// Outer glow sphere
function GlowSphere({ mood }: { mood: AvatarMood }) {
  const colors = MOOD_COLORS[mood];

  return (
    <mesh>
      <sphereGeometry args={[2, 32, 32]} />
      <meshStandardMaterial
        color={colors.secondary}
        transparent
        opacity={0.05}
        side={THREE.BackSide}
      />
    </mesh>
  );
}

// Sparkle effects
function SparkleCloud({ mood, moodIntensity }: { mood: AvatarMood; moodIntensity: number }) {
  const colors = MOOD_COLORS[mood];
  const count = mood === 'excited' ? 100 : mood === 'speaking' ? 60 : 40;

  return (
    <Sparkles
      count={count}
      scale={3}
      size={2 + moodIntensity * 2}
      speed={0.4 + moodIntensity * 0.3}
      color={colors.primary}
      opacity={0.6}
    />
  );
}

// Inner scene
function AvatarScene() {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';
  const colors = MOOD_COLORS[mood];

  // Calculate mood intensity
  const moodIntensity = useMemo(() => {
    switch (mood) {
      case 'idle': return 0.2;
      case 'thinking': return 0.5;
      case 'speaking': return 0.7;
      case 'excited': return 1.0;
      default: return 0.2;
    }
  }, [mood]);

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.4} />
      <pointLight position={[5, 5, 5]} intensity={1} color={colors.primary} />
      <pointLight position={[-5, -5, 5]} intensity={0.5} color={colors.secondary} />
      <spotLight
        position={[0, 5, 0]}
        angle={0.3}
        penumbra={1}
        intensity={0.5}
        color={colors.emissive}
      />

      {/* Main core */}
      <CoreEntity mood={mood} moodIntensity={moodIntensity} />

      {/* Orbiting rings */}
      <OrbitingRing
        radius={1.8}
        count={12}
        size={0.04}
        color={colors.primary}
        speed={0.5}
      />
      <OrbitingRing
        radius={2.2}
        count={16}
        size={0.03}
        color={colors.secondary}
        speed={-0.3}
        yOffset={0.3}
      />
      <OrbitingRing
        radius={1.5}
        count={8}
        size={0.05}
        color={colors.emissive}
        speed={0.7}
        yOffset={-0.2}
      />

      {/* Energy trails (when active) */}
      {(mood === 'speaking' || mood === 'excited') && (
        <>
          <EnergyTrail mood={mood} />
          <EnergyTrail mood={mood} />
        </>
      )}

      {/* Sparkles */}
      <SparkleCloud mood={mood} moodIntensity={moodIntensity} />

      {/* Outer glow */}
      <GlowSphere mood={mood} />

      {/* Environment for reflections */}
      <Environment preset="night" />
    </>
  );
}

// Main exported component with status indicator
export function Avatar3D({ compact = false }: { compact?: boolean }) {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';
  const colors = MOOD_COLORS[mood];

  const statusText = useMemo(() => {
    switch (mood) {
      case 'speaking': return 'TRANSMITTING';
      case 'thinking': return 'PROCESSING';
      case 'excited': return 'READY';
      default: return 'LISTENING';
    }
  }, [mood]);

  const size = compact ? 'w-24 h-24' : 'w-[200px] h-[200px]';

  return (
    <div className="flex flex-col items-center">
      {/* 3D Canvas */}
      <div className={`${size} relative`}>
        <Canvas
          camera={{ position: [0, 0, 5], fov: 45 }}
          gl={{ antialias: true, alpha: true }}
          style={{ background: 'transparent' }}
        >
          <AvatarScene />
        </Canvas>

        {/* Glow overlay */}
        <div
          className="absolute inset-[-20%] rounded-full blur-2xl pointer-events-none opacity-30"
          style={{
            background: `radial-gradient(circle, ${colors.primary}40 0%, transparent 70%)`,
          }}
        />
      </div>

      {/* Status indicator (only for full size) */}
      {!compact && (
        <div className="mt-4 flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: colors.primary }}
          />
          <span
            className="text-xs font-mono tracking-widest uppercase opacity-70"
            style={{ color: colors.primary }}
          >
            {statusText}
          </span>
        </div>
      )}
    </div>
  );
}

// Compact version for chat header
export function Avatar3DCompact() {
  return <Avatar3D compact />;
}
