/**
 * TypeScript types for the particle face avatar
 */

import type { AvatarMood } from '@/stores/uiPhaseStore';
import * as THREE from 'three';

/**
 * Configuration for a specific mood state
 */
export interface MoodConfig {
  /** Animation intensity (0.0 - 1.0) */
  intensity: number;
  /** Animation speed multiplier */
  speed: number;
  /** Base color for particles */
  color: THREE.Color;
}

/**
 * Map of mood states to their configurations
 */
export type MoodConfigMap = Record<AvatarMood, MoodConfig>;

/**
 * Props for the ParticleFace component
 */
export interface ParticleFaceProps {
  /** Current mood state */
  mood: AvatarMood;
  /** Compact mode (fewer particles) */
  compact?: boolean;
}

/**
 * Props for the main Avatar3DCanvas component
 */
export interface Avatar3DCanvasProps {
  /** Compact mode for smaller display */
  compact?: boolean;
}

/**
 * Shader uniform values
 */
export interface ParticleUniforms {
  uTime: { value: number };
  uIntensity: { value: number };
  uSpeed: { value: number };
  uColor: { value: THREE.Color };
  uMouse: { value: THREE.Vector2 };
  uMouseRadius: { value: number };
  uTouchTrail: { value: THREE.Texture | null };
}

/**
 * Configuration for face region distribution
 */
export interface FaceRegion {
  /** Weight for this region (0-1, all weights sum to 1) */
  weight: number;
  /** Function to generate a point in this region */
  generate: () => [number, number, number];
}
