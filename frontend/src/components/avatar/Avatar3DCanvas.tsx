/**
 * Avatar3DCanvas - Enhanced Flowing Particle Face with GLSL Shaders
 *
 * 7000 particles animated on GPU using curl noise.
 * Features:
 * - Curl noise displacement for organic flow
 * - Mouse interaction (repel particles)
 * - Touch trail effect
 * - Mood-based animation parameters
 *
 * Inspired by: https://tympanus.net/codrops/2019/01/17/interactive-particles-with-three-js/
 */
import { useRef, useMemo, useEffect, useCallback } from 'react';
import { Canvas, useFrame, ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import { useUIPhaseStore, AvatarMood } from '@/stores/uiPhaseStore';

// Import shaders
import vertexShader from './shaders/particleFace.vert';
import fragmentShader from './shaders/particleFace.frag';

// Import hooks
import { useParticleGeometry } from './hooks/useParticleGeometry';
import { useTouchTrail } from './hooks/useTouchTrail';

// Import types
import type { MoodConfigMap, Avatar3DCanvasProps } from './types';

// Mood configurations
const MOOD_CONFIG: MoodConfigMap = {
  idle: {
    intensity: 0.2,
    speed: 0.3,
    color: new THREE.Color('#67e8f9'), // cyan
  },
  thinking: {
    intensity: 0.5,
    speed: 0.6,
    color: new THREE.Color('#a5b4fc'), // indigo
  },
  speaking: {
    intensity: 0.8,
    speed: 1.2,
    color: new THREE.Color('#86efac'), // green
  },
  excited: {
    intensity: 1.0,
    speed: 1.8,
    color: new THREE.Color('#f0abfc'), // pink
  },
};

// Mood colors for CSS (used in glow effect)
const MOOD_COLORS: Record<AvatarMood, THREE.Color> = {
  idle: new THREE.Color('#67e8f9'),
  thinking: new THREE.Color('#a5b4fc'),
  speaking: new THREE.Color('#86efac'),
  excited: new THREE.Color('#f0abfc'),
};

interface ParticleFaceProps {
  mood: AvatarMood;
  compact?: boolean;
}

/**
 * Main particle system using ShaderMaterial
 */
function ParticleFace({ mood, compact = false }: ParticleFaceProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const mouseRef = useRef(new THREE.Vector2(0, 0));
  const targetMouseRef = useRef(new THREE.Vector2(0, 0));

  // Particle count based on mode
  const particleCount = compact ? 3000 : 7000;

  // Get geometry from hook
  const geometry = useParticleGeometry(particleCount);

  // Get touch trail from hook
  const { texture: touchTrail, updateTrail } = useTouchTrail(64);

  // Create uniforms
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uIntensity: { value: MOOD_CONFIG.idle.intensity },
    uSpeed: { value: MOOD_CONFIG.idle.speed },
    uColor: { value: MOOD_CONFIG.idle.color.clone() },
    uMouse: { value: new THREE.Vector2(0, 0) },
    uMouseRadius: { value: 0.4 },
    uTouchTrail: { value: touchTrail },
  }), [touchTrail]);

  // Update uniforms when mood changes
  useEffect(() => {
    const config = MOOD_CONFIG[mood];
    uniforms.uIntensity.value = config.intensity;
    uniforms.uSpeed.value = config.speed;
    uniforms.uColor.value.copy(config.color);
  }, [mood, uniforms]);

  // Update touch trail texture reference
  useEffect(() => {
    uniforms.uTouchTrail.value = touchTrail;
  }, [touchTrail, uniforms]);

  // Animation loop
  useFrame((state) => {
    // Update time
    uniforms.uTime.value = state.clock.elapsedTime;

    // Smooth mouse movement (lerp)
    mouseRef.current.lerp(targetMouseRef.current, 0.1);
    uniforms.uMouse.value.copy(mouseRef.current);

    // Update touch trail with current mouse position
    updateTrail(mouseRef.current.x, mouseRef.current.y);

    // Subtle mesh rotation for depth perception
    if (pointsRef.current) {
      pointsRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.2) * 0.05;
      pointsRef.current.rotation.x = Math.cos(state.clock.elapsedTime * 0.15) * 0.02;
    }
  });

  // Mouse move handler
  const handlePointerMove = useCallback((e: ThreeEvent<PointerEvent>) => {
    // Convert point to normalized coordinates (-1 to 1)
    targetMouseRef.current.set(
      (e.point.x / 0.9) * 2,
      (e.point.y / 0.9) * 2
    );
  }, []);

  // Mouse leave handler
  const handlePointerLeave = useCallback(() => {
    // Return mouse to center gradually
    targetMouseRef.current.set(0, 0);
  }, []);

  return (
    <points
      ref={pointsRef}
      geometry={geometry}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <shaderMaterial
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/**
 * Glow background effect
 */
function GlowBackground({ mood }: { mood: AvatarMood }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = MOOD_COLORS[mood];

  useFrame((state) => {
    if (meshRef.current) {
      const material = meshRef.current.material as THREE.MeshBasicMaterial;
      material.opacity = 0.03 + Math.sin(state.clock.elapsedTime * 0.8) * 0.015;
      meshRef.current.scale.setScalar(1.8 + Math.sin(state.clock.elapsedTime * 0.5) * 0.1);
    }
  });

  return (
    <mesh ref={meshRef} position={[0, 0, -0.3]}>
      <circleGeometry args={[1, 64]} />
      <meshBasicMaterial color={color} transparent opacity={0.04} />
    </mesh>
  );
}

/**
 * Floating accent particles orbiting around the face
 */
function FloatingStrokes({ mood, compact }: { mood: AvatarMood; compact?: boolean }) {
  const groupRef = useRef<THREE.Group>(null);
  const color = MOOD_COLORS[mood];

  const strokes = useMemo(() => {
    const count = compact ? 20 : 40;
    const arr = [];
    for (let i = 0; i < count; i++) {
      arr.push({
        angle: Math.random() * Math.PI * 2,
        radius: 0.9 + Math.random() * 0.5,
        speed: 0.1 + Math.random() * 0.2,
        phase: Math.random() * Math.PI * 2,
        y: (Math.random() - 0.5) * 1.5,
        scale: 0.01 + Math.random() * 0.01,
      });
    }
    return arr;
  }, [compact]);

  useFrame((state) => {
    if (!groupRef.current) return;
    const time = state.clock.elapsedTime;

    groupRef.current.children.forEach((child, i) => {
      const s = strokes[i];
      const angle = s.angle + time * s.speed;
      child.position.x = Math.cos(angle) * s.radius;
      child.position.z = Math.sin(angle) * s.radius * 0.3;
      child.position.y = s.y + Math.sin(time * 0.5 + s.phase) * 0.15;
      child.rotation.z = angle + Math.PI / 2;
      const scale = s.scale * (1 + Math.sin(time + s.phase) * 0.3);
      child.scale.set(scale * 3, scale, scale);
    });
  });

  return (
    <group ref={groupRef}>
      {strokes.map((_, i) => (
        <mesh key={i}>
          <boxGeometry args={[1, 1, 0.2]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.15}
          />
        </mesh>
      ))}
    </group>
  );
}

/**
 * Invisible interaction plane for mouse events
 */
function InteractionPlane() {
  return (
    <mesh position={[0, 0, 0.2]} visible={false}>
      <planeGeometry args={[3, 3]} />
      <meshBasicMaterial transparent opacity={0} />
    </mesh>
  );
}

/**
 * Main scene composition
 */
function AvatarScene({ compact = false }: { compact?: boolean }) {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';

  return (
    <>
      <GlowBackground mood={mood} />
      <ParticleFace mood={mood} compact={compact} />
      <FloatingStrokes mood={mood} compact={compact} />
      <InteractionPlane />
    </>
  );
}

/**
 * Main exported component
 */
export default function Avatar3DCanvas({ compact = false }: Avatar3DCanvasProps) {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';
  const color = MOOD_COLORS[mood];

  const statusText = useMemo(() => {
    switch (mood) {
      case 'speaking': return 'SPEAKING';
      case 'thinking': return 'THINKING';
      case 'excited': return 'READY';
      default: return 'LISTENING';
    }
  }, [mood]);

  const size = compact ? 'w-24 h-24' : 'w-[320px] h-[320px]';

  return (
    <div className="flex flex-col items-center">
      <div className={`${size} relative`}>
        <Canvas
          camera={{ position: [0, 0, 2], fov: 50 }}
          gl={{
            antialias: true,
            alpha: true,
            powerPreference: 'high-performance',
          }}
          style={{ background: 'transparent' }}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
          }}
        >
          <AvatarScene compact={compact} />
        </Canvas>

        {/* Soft outer glow */}
        <div
          className="absolute inset-[-10%] rounded-full blur-3xl pointer-events-none -z-10 opacity-30"
          style={{
            background: `radial-gradient(circle, #${color.getHexString()}40 0%, transparent 70%)`
          }}
        />
      </div>

      {/* Status indicator (full size only) */}
      {!compact && (
        <div className="mt-1 flex items-center gap-2 opacity-40">
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ backgroundColor: `#${color.getHexString()}` }}
          />
          <span
            className="text-[10px] font-light tracking-widest uppercase"
            style={{ color: `#${color.getHexString()}` }}
          >
            {statusText}
          </span>
        </div>
      )}
    </div>
  );
}
