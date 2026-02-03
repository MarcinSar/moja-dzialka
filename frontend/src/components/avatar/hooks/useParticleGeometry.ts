/**
 * useParticleGeometry - Generates instanced buffer geometry for particle face
 *
 * Creates 7000 particles distributed in a face shape with:
 * - aBasePosition: Face distribution positions
 * - aPhase: Random phase offsets for animation
 * - aScale: Random scale factors
 */

import { useMemo } from 'react';
import * as THREE from 'three';
import type { FaceRegion } from '../types';

/**
 * Generate face-shaped distribution of particle positions
 */
function generateFaceDistribution(count: number): Float32Array {
  const positions = new Float32Array(count * 3);
  let idx = 0;

  // Face regions with different densities
  const regions: FaceRegion[] = [
    // Face outline (oval) - 30%
    {
      weight: 0.30,
      generate: () => {
        const angle = Math.random() * Math.PI * 2;
        const r = 0.7 + Math.random() * 0.15;
        const stretch = 1.2 + Math.random() * 0.1;
        return [
          Math.sin(angle) * r * 0.85,
          Math.cos(angle) * r * stretch,
          (Math.random() - 0.5) * 0.2
        ];
      }
    },
    // Left eye area - 12%
    {
      weight: 0.12,
      generate: () => {
        const angle = Math.random() * Math.PI * 2;
        const r = Math.random() * 0.12;
        return [
          -0.22 + Math.cos(angle) * r,
          0.22 + Math.sin(angle) * r * 0.6,
          0.1 + Math.random() * 0.05
        ];
      }
    },
    // Right eye area - 12%
    {
      weight: 0.12,
      generate: () => {
        const angle = Math.random() * Math.PI * 2;
        const r = Math.random() * 0.12;
        return [
          0.22 + Math.cos(angle) * r,
          0.22 + Math.sin(angle) * r * 0.6,
          0.1 + Math.random() * 0.05
        ];
      }
    },
    // Nose area - 8%
    {
      weight: 0.08,
      generate: () => {
        const t = Math.random();
        return [
          (Math.random() - 0.5) * 0.06,
          0.1 - t * 0.35,
          0.15 + t * 0.08
        ];
      }
    },
    // Mouth area - 15%
    {
      weight: 0.15,
      generate: () => {
        const t = Math.random();
        const curve = Math.sin(t * Math.PI) * 0.06;
        return [
          (t - 0.5) * 0.35,
          -0.35 + curve,
          0.08 + Math.random() * 0.03
        ];
      }
    },
    // Cheeks - 10%
    {
      weight: 0.10,
      generate: () => {
        const side = Math.random() > 0.5 ? 1 : -1;
        return [
          side * (0.35 + Math.random() * 0.15),
          -0.05 + (Math.random() - 0.5) * 0.25,
          0.05 + Math.random() * 0.1
        ];
      }
    },
    // Forehead - 8%
    {
      weight: 0.08,
      generate: () => {
        return [
          (Math.random() - 0.5) * 0.5,
          0.55 + Math.random() * 0.2,
          (Math.random() - 0.5) * 0.15
        ];
      }
    },
    // Ambient particles around face - 5%
    {
      weight: 0.05,
      generate: () => {
        const angle = Math.random() * Math.PI * 2;
        const r = 0.9 + Math.random() * 0.4;
        return [
          Math.sin(angle) * r,
          Math.cos(angle) * r * 1.1,
          (Math.random() - 0.5) * 0.4
        ];
      }
    },
  ];

  for (let i = 0; i < count; i++) {
    const rand = Math.random();
    let cumWeight = 0;
    let point: [number, number, number] = [0, 0, 0];

    for (const region of regions) {
      cumWeight += region.weight;
      if (rand <= cumWeight) {
        point = region.generate();
        break;
      }
    }

    positions[idx++] = point[0];
    positions[idx++] = point[1];
    positions[idx++] = point[2];
  }

  return positions;
}

/**
 * Hook to create particle geometry
 *
 * @param count - Number of particles (default 7000)
 * @returns THREE.BufferGeometry with instanced attributes
 */
export function useParticleGeometry(count: number = 7000): THREE.BufferGeometry {
  return useMemo(() => {
    const geometry = new THREE.BufferGeometry();

    // Generate face distribution positions
    const positions = generateFaceDistribution(count);

    // Create phase offsets (for desynchronized animation)
    const phases = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      phases[i] = Math.random() * Math.PI * 2;
    }

    // Create scale factors (for size variation)
    const scales = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      scales[i] = 0.4 + Math.random() * 0.6; // 0.4 to 1.0
    }

    // Set attributes
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('aBasePosition', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
    geometry.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));

    return geometry;
  }, [count]);
}
