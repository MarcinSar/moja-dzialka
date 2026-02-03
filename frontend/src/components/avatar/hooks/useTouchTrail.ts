/**
 * useTouchTrail - Manages a canvas texture for mouse/touch trail effects
 *
 * Creates a 64x64 canvas texture that records cursor movement
 * with gradual fade for smooth trail effects.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import * as THREE from 'three';

interface TouchTrailResult {
  /** The canvas texture for use in shaders */
  texture: THREE.CanvasTexture | null;
  /** Update the trail with current mouse position */
  updateTrail: (mouseX: number, mouseY: number) => void;
  /** Clear the trail */
  clearTrail: () => void;
}

/**
 * Hook to create and manage touch trail texture
 *
 * @param resolution - Canvas resolution (default 64)
 * @returns Object with texture and update function
 */
export function useTouchTrail(resolution: number = 64): TouchTrailResult {
  const [texture, setTexture] = useState<THREE.CanvasTexture | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const lastPosRef = useRef<{ x: number; y: number } | null>(null);

  // Initialize canvas and texture
  useEffect(() => {
    const canvas = document.createElement('canvas');
    canvas.width = resolution;
    canvas.height = resolution;
    canvasRef.current = canvas;

    const ctx = canvas.getContext('2d', { willReadFrequently: false });
    if (!ctx) {
      console.warn('[useTouchTrail] Could not get 2D context');
      return;
    }
    ctxRef.current = ctx;

    // Initialize with black
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, resolution, resolution);

    // Create texture
    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.wrapS = THREE.ClampToEdgeWrapping;
    tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.needsUpdate = true;

    setTexture(tex);

    // Cleanup
    return () => {
      tex.dispose();
      canvasRef.current = null;
      ctxRef.current = null;
    };
  }, [resolution]);

  /**
   * Update the trail with a new point
   * @param mouseX - Mouse X in normalized coords (-1 to 1)
   * @param mouseY - Mouse Y in normalized coords (-1 to 1)
   */
  const updateTrail = useCallback((mouseX: number, mouseY: number) => {
    const ctx = ctxRef.current;
    const canvas = canvasRef.current;
    if (!ctx || !canvas || !texture) return;

    // Convert from normalized coords to canvas coords
    const x = (mouseX * 0.5 + 0.5) * resolution;
    const y = (1 - (mouseY * 0.5 + 0.5)) * resolution; // Flip Y

    // Fade existing content
    ctx.fillStyle = 'rgba(0, 0, 0, 0.03)';
    ctx.fillRect(0, 0, resolution, resolution);

    // Draw line from last position for smooth trails
    if (lastPosRef.current) {
      const gradient = ctx.createRadialGradient(
        x, y, 0,
        x, y, 12
      );
      gradient.addColorStop(0, 'rgba(255, 255, 255, 0.8)');
      gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.3)');
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(x, y, 12, 0, Math.PI * 2);
      ctx.fill();

      // Draw connecting line for continuous trails
      const dx = x - lastPosRef.current.x;
      const dy = y - lastPosRef.current.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist > 2 && dist < 50) {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 6;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(lastPosRef.current.x, lastPosRef.current.y);
        ctx.lineTo(x, y);
        ctx.stroke();
      }
    } else {
      // First point - just draw a dot
      const gradient = ctx.createRadialGradient(
        x, y, 0,
        x, y, 10
      );
      gradient.addColorStop(0, 'rgba(255, 255, 255, 0.6)');
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(x, y, 10, 0, Math.PI * 2);
      ctx.fill();
    }

    // Store current position
    lastPosRef.current = { x, y };

    // Mark texture for update
    texture.needsUpdate = true;
  }, [resolution, texture]);

  /**
   * Clear the trail completely
   */
  const clearTrail = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx || !texture) return;

    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, resolution, resolution);
    lastPosRef.current = null;
    texture.needsUpdate = true;
  }, [resolution, texture]);

  return { texture, updateTrail, clearTrail };
}
