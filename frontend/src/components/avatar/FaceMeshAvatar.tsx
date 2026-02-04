/**
 * FaceMeshAvatar - Interactive wireframe face mesh avatar
 *
 * Renders a 468-point canonical face mesh (MediaPipe) as a sci-fi
 * wireframe with animated expressions, horizontal scan line, and
 * mood-reactive colors. Inspired by face recognition visualization
 * (dots at landmarks connected by lines).
 *
 * Layers:
 *  1. Full tessellation wireframe (2556 edges, low opacity)
 *  2. Feature contours (eyes, lips, brows, jawline — brighter)
 *  3. Landmark dots (468 vertices, importance-based sizing)
 *  4. Scan line (horizontal bright sweep)
 *  5. Background glow circle
 *
 * Expressions: blink, mouth open, smile, brow raise/furrow
 * driven by mood state (idle, thinking, speaking, excited).
 */
import { useRef, useMemo, useCallback, useEffect } from 'react';
import { Canvas, useFrame, ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import { useUIPhaseStore, AvatarMood } from '@/stores/uiPhaseStore';

// Shaders
import wireVert from './shaders/faceMeshWire.vert';
import wireFrag from './shaders/faceMeshWire.frag';
import dotVert from './shaders/faceMeshDot.vert';
import dotFrag from './shaders/faceMeshDot.frag';

// Face mesh data
import {
  CANONICAL_FACE_VERTICES,
  FACEMESH_TESSELATION,
  FACE_VERTEX_COUNT,
  FACE_REGION_LEFTEYE,
  FACE_REGION_RIGHTEYE,
  FACE_REGION_LIPSOUTER,
  FACE_REGION_LIPSLOWEROUTER,
  FACE_REGION_LIPSUPPEROUTER,
  FACE_REGION_LIPSLOWERINNER,
  FACE_REGION_LIPSUPPERINNER,
  FACE_REGION_LEFTEYEBROW,
  FACE_REGION_RIGHTEYEBROW,
  FACE_REGION_FACEOVAL,
  FACE_REGION_NOSEBRIDGE,
  FACE_REGION_NOSEBOTTOM,
  LIPS_CONNECTIONS,
  LEFT_EYE_CONNECTIONS,
  RIGHT_EYE_CONNECTIONS,
  LEFT_EYEBROW_CONNECTIONS,
  RIGHT_EYEBROW_CONNECTIONS,
  FACE_OVAL_CONNECTIONS,
} from './faceMeshData';

// ─── Mood config ─────────────────────────────────────────────

interface MoodCfg { intensity: number; speed: number; color: THREE.Color }

const MOOD: Record<AvatarMood, MoodCfg> = {
  idle:     { intensity: 0.3, speed: 0.3, color: new THREE.Color('#67e8f9') },
  thinking: { intensity: 0.6, speed: 0.5, color: new THREE.Color('#a5b4fc') },
  speaking: { intensity: 0.8, speed: 1.0, color: new THREE.Color('#86efac') },
  excited:  { intensity: 1.0, speed: 1.5, color: new THREE.Color('#f0abfc') },
};

// ─── Mesh utilities ──────────────────────────────────────────

function normalizeVertices(src: Float32Array): Float32Array {
  const out = new Float32Array(src.length);
  let mnX = Infinity, mxX = -Infinity;
  let mnY = Infinity, mxY = -Infinity;
  let mnZ = Infinity, mxZ = -Infinity;

  for (let i = 0; i < src.length; i += 3) {
    const x = src[i], y = src[i + 1], z = src[i + 2];
    if (x < mnX) mnX = x; if (x > mxX) mxX = x;
    if (y < mnY) mnY = y; if (y > mxY) mxY = y;
    if (z < mnZ) mnZ = z; if (z > mxZ) mxZ = z;
  }

  const cx = (mnX + mxX) / 2;
  const cy = (mnY + mxY) / 2;
  const cz = (mnZ + mxZ) / 2;
  const scale = 2.0 / Math.max(mxX - mnX, mxY - mnY);

  for (let i = 0; i < src.length; i += 3) {
    out[i]     = (src[i] - cx) * scale;
    out[i + 1] = (src[i + 1] - cy) * scale;
    out[i + 2] = (src[i + 2] - cz) * scale;
  }
  return out;
}

function buildImportance(): Float32Array {
  const imp = new Float32Array(FACE_VERTEX_COUNT).fill(0.12);
  const s = (indices: number[], v: number) => {
    for (const i of indices) if (i < FACE_VERTEX_COUNT) imp[i] = Math.max(imp[i], v);
  };
  s(FACE_REGION_LEFTEYE, 0.6);
  s(FACE_REGION_RIGHTEYE, 0.6);
  s(FACE_REGION_LIPSOUTER, 0.5);
  s(FACE_REGION_LEFTEYEBROW, 0.65);
  s(FACE_REGION_RIGHTEYEBROW, 0.65);
  s(FACE_REGION_FACEOVAL, 0.55);
  s(FACE_REGION_NOSEBRIDGE, 0.35);
  s(FACE_REGION_NOSEBOTTOM, 0.3);
  return imp;
}

function buildFeatureIndices(): Uint16Array {
  const edges = [
    ...LIPS_CONNECTIONS,
    ...LEFT_EYE_CONNECTIONS,
    ...RIGHT_EYE_CONNECTIONS,
    ...LEFT_EYEBROW_CONNECTIONS,
    ...RIGHT_EYEBROW_CONNECTIONS,
    ...FACE_OVAL_CONNECTIONS,
  ].filter(i => i < FACE_VERTEX_COUNT);
  return new Uint16Array(edges);
}

function buildTessIndices(): Uint16Array {
  const valid: number[] = [];
  for (let i = 0; i < FACEMESH_TESSELATION.length; i += 2) {
    const a = FACEMESH_TESSELATION[i], b = FACEMESH_TESSELATION[i + 1];
    if (a < FACE_VERTEX_COUNT && b < FACE_VERTEX_COUNT) valid.push(a, b);
  }
  return new Uint16Array(valid);
}

// ─── Expression engine ───────────────────────────────────────

interface Weights {
  blinkL: number;
  blinkR: number;
  mouthOpen: number;
  smile: number;
  browUp: number;
  browFurrow: number;
}

function regionCenterY(base: Float32Array, indices: number[]): number {
  let sum = 0, n = 0;
  for (const i of indices) {
    if (i < FACE_VERTEX_COUNT) { sum += base[i * 3 + 1]; n++; }
  }
  return n > 0 ? sum / n : 0;
}

function applyExpressions(out: Float32Array, base: Float32Array, w: Weights) {
  // Start from base
  out.set(base);

  // Blink — move eye vertices toward region center Y
  const blink = (indices: number[], amount: number) => {
    if (amount < 0.01) return;
    const cy = regionCenterY(base, indices);
    for (const i of indices) {
      if (i >= FACE_VERTEX_COUNT) continue;
      out[i * 3 + 1] = base[i * 3 + 1] + (cy - base[i * 3 + 1]) * amount * 0.85;
    }
  };
  blink(FACE_REGION_LEFTEYE, w.blinkL);
  blink(FACE_REGION_RIGHTEYE, w.blinkR);

  // Mouth open — lower lip down, upper lip up, jaw hint
  if (w.mouthOpen > 0.01) {
    const m = w.mouthOpen;
    for (const i of FACE_REGION_LIPSLOWEROUTER) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] -= m * 0.10;
    for (const i of FACE_REGION_LIPSLOWERINNER) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] -= m * 0.08;
    for (const i of FACE_REGION_LIPSUPPEROUTER) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] += m * 0.025;
    for (const i of FACE_REGION_LIPSUPPERINNER) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] += m * 0.02;
    // Chin/jaw vertices follow lower lip slightly
    for (const i of [152, 377, 400, 148, 176]) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] -= m * 0.04;
  }

  // Smile — lip corners outward and up (amplified)
  if (w.smile > 0.01) {
    const s = w.smile;
    // Corner landmarks (stronger displacement)
    if (61 < FACE_VERTEX_COUNT) {
      out[61 * 3] -= s * 0.05;
      out[61 * 3 + 1] += s * 0.035;
    }
    if (291 < FACE_VERTEX_COUNT) {
      out[291 * 3] += s * 0.05;
      out[291 * 3 + 1] += s * 0.035;
    }
    // Surrounding lip vertices + cheek raise
    for (const i of [146, 91, 185, 40]) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] += s * 0.02;
    for (const i of [375, 321, 409, 270]) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] += s * 0.02;
    // Cheeks raise slightly during smile (nasolabial fold area)
    for (const i of [205, 425, 187, 411]) if (i < FACE_VERTEX_COUNT) {
      out[i * 3 + 1] += s * 0.015;
      out[i * 3 + 2] += s * 0.01;
    }
  }

  // Brow raise (amplified)
  if (w.browUp > 0.01) {
    const b = w.browUp;
    for (const i of [...FACE_REGION_LEFTEYEBROW, ...FACE_REGION_RIGHTEYEBROW]) {
      if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] += b * 0.07;
    }
    // Forehead area follows brow raise subtly
    for (const i of [10, 151, 9, 8]) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] += b * 0.02;
  }

  // Brow furrow — inner brows down and inward (amplified)
  if (w.browFurrow > 0.01) {
    const f = w.browFurrow;
    for (const i of [285, 295]) if (i < FACE_VERTEX_COUNT) {
      out[i * 3 + 1] -= f * 0.04;
      out[i * 3] -= f * 0.015;
    }
    for (const i of [55, 65]) if (i < FACE_VERTEX_COUNT) {
      out[i * 3 + 1] -= f * 0.04;
      out[i * 3] += f * 0.015;
    }
    // Glabella compression
    for (const i of [9, 168]) if (i < FACE_VERTEX_COUNT) out[i * 3 + 1] -= f * 0.015;
  }
}

// ─── Animation controller ────────────────────────────────────

class Animator {
  w: Weights = { blinkL: 0, blinkR: 0, mouthOpen: 0, smile: 0, browUp: 0, browFurrow: 0 };
  private tgt: Weights = { ...this.w };
  private nextBlink = 1.5 + Math.random() * 2.5;
  private blinkT = 0;
  private isDoubleBlink = false;
  private doubleBlinksLeft = 0;
  // Idle micro-expression system
  private nextIdleShift = 1 + Math.random() * 3;
  private idleSmileTarget = 0.05;
  private idleBrowTarget = 0;
  private idleMouthTarget = 0;
  // Head micro-tilt offsets (accessed by scene)
  headTiltX = 0;
  headTiltY = 0;
  private headTargetX = 0;
  private headTargetY = 0;
  private nextHeadShift = 2 + Math.random() * 4;

  update(dt: number, time: number, mood: AvatarMood) {
    dt = Math.min(dt, 0.05);

    // ── Idle micro-expressions ──
    this.nextIdleShift -= dt;
    if (this.nextIdleShift <= 0) {
      this.nextIdleShift = 2 + Math.random() * 5;
      // Randomly shift idle expression targets
      this.idleSmileTarget = 0.02 + Math.random() * 0.12;
      this.idleBrowTarget = (Math.random() - 0.5) * 0.15;
      this.idleMouthTarget = Math.random() < 0.3 ? Math.random() * 0.04 : 0;
    }

    // ── Head micro-movements ──
    this.nextHeadShift -= dt;
    if (this.nextHeadShift <= 0) {
      this.nextHeadShift = 1.5 + Math.random() * 3;
      this.headTargetX = (Math.random() - 0.5) * 0.06;
      this.headTargetY = (Math.random() - 0.5) * 0.04;
    }
    this.headTiltX += (this.headTargetX - this.headTiltX) * dt * 1.5;
    this.headTiltY += (this.headTargetY - this.headTiltY) * dt * 1.5;

    // ── Mood-driven expression targets ──
    switch (mood) {
      case 'idle': {
        // Use micro-expression targets for variety
        this.tgt.smile = this.idleSmileTarget;
        this.tgt.mouthOpen = this.idleMouthTarget;
        this.tgt.browUp = this.idleBrowTarget > 0 ? this.idleBrowTarget : 0;
        this.tgt.browFurrow = this.idleBrowTarget < 0 ? -this.idleBrowTarget : 0;
        // Subtle rhythmic overlay
        this.tgt.smile += Math.sin(time * 0.3) * 0.02;
        break;
      }
      case 'thinking': {
        this.tgt.smile = 0;
        this.tgt.mouthOpen = Math.max(0, Math.sin(time * 0.7) * 0.02);
        this.tgt.browFurrow = 0.3 + Math.sin(time * 1.1) * 0.1;
        this.tgt.browUp = 0;
        // Occasional lip purse
        if (Math.sin(time * 0.5) > 0.8) this.tgt.mouthOpen = 0.03;
        break;
      }
      case 'speaking': {
        // Multi-layered mouth movement for natural speech
        const primary = Math.sin(time * 8) * 0.25;
        const secondary = Math.sin(time * 12.7) * 0.12;
        const tertiary = Math.sin(time * 5.3) * 0.08;
        const pauses = Math.sin(time * 1.8) > 0.6 ? 0.7 : 1.0; // natural speech pauses
        this.tgt.mouthOpen = Math.max(0, (0.25 + primary + secondary + tertiary) * pauses);
        this.tgt.smile = 0.1 + Math.sin(time * 0.9) * 0.08;
        this.tgt.browFurrow = 0;
        this.tgt.browUp = 0.08 + Math.sin(time * 2.3) * 0.06;
        break;
      }
      case 'excited': {
        this.tgt.smile = 0.5 + Math.sin(time * 2) * 0.1;
        this.tgt.browUp = 0.3 + Math.sin(time * 1.5) * 0.1;
        this.tgt.mouthOpen = Math.max(0, 0.08 + Math.sin(time * 3.5) * 0.06);
        this.tgt.browFurrow = 0;
        break;
      }
    }

    // ── Autonomous blink system with asymmetry ──
    this.nextBlink -= dt;
    if (this.nextBlink <= 0 && this.blinkT === 0) {
      this.blinkT = 0.001;
      // Double blink 20% of the time
      if (!this.isDoubleBlink && Math.random() < 0.2) {
        this.isDoubleBlink = true;
        this.doubleBlinksLeft = 1;
      }
      this.nextBlink = 2.0 + Math.random() * 4.5;
      // More frequent blinking when speaking
      if (mood === 'speaking') this.nextBlink *= 0.6;
    }
    if (this.blinkT > 0) {
      this.blinkT += dt * 10; // slightly faster blinks
      const bv = this.blinkT < 1.2
        ? Math.min(this.blinkT / 1.2, 1)
        : Math.max(0, (2.4 - this.blinkT) / 1.2);
      // Slight asymmetry — one eye leads by a tiny bit
      this.tgt.blinkL = bv;
      this.tgt.blinkR = Math.max(0, bv - 0.05);
      if (this.blinkT >= 2.4) {
        this.blinkT = 0;
        this.tgt.blinkL = 0;
        this.tgt.blinkR = 0;
        // Handle double blink
        if (this.isDoubleBlink && this.doubleBlinksLeft > 0) {
          this.doubleBlinksLeft--;
          this.nextBlink = 0.15; // quick follow-up
        } else {
          this.isDoubleBlink = false;
        }
      }
    }

    // ── Smooth interpolation toward targets ──
    const r = Math.min(dt * 6, 1);
    for (const k of Object.keys(this.w) as (keyof Weights)[]) {
      this.w[k] += (this.tgt[k] - this.w[k]) * r;
    }
  }
}

// ─── Scene ───────────────────────────────────────────────────

function FaceMeshScene({ compact = false }: { compact?: boolean }) {
  const mood = useUIPhaseStore((s) => s.avatarMood) || 'idle';
  const groupRef = useRef<THREE.Group>(null);
  const mouseRef = useRef(new THREE.Vector2(0, 0));
  const targetMouse = useRef(new THREE.Vector2(0, 0));
  const scanRef = useRef<THREE.Mesh>(null);

  // Static data (computed once)
  const { base, anim, tessIdx, featIdx, importance } = useMemo(() => ({
    base: normalizeVertices(CANONICAL_FACE_VERTICES),
    anim: normalizeVertices(CANONICAL_FACE_VERTICES),
    tessIdx: buildTessIndices(),
    featIdx: buildFeatureIndices(),
    importance: buildImportance(),
  }), []);

  const animator = useMemo(() => new Animator(), []);

  // Geometries — all share the same position BufferAttribute
  const { tessGeom, featGeom, dotGeom, posAttr } = useMemo(() => {
    const pa = new THREE.BufferAttribute(anim, 3);

    const tg = new THREE.BufferGeometry();
    tg.setAttribute('position', pa);
    tg.setIndex(new THREE.BufferAttribute(tessIdx, 1));

    const fg = new THREE.BufferGeometry();
    fg.setAttribute('position', pa);
    fg.setIndex(new THREE.BufferAttribute(featIdx, 1));

    const dg = new THREE.BufferGeometry();
    dg.setAttribute('position', pa);
    dg.setAttribute('aImportance', new THREE.BufferAttribute(importance, 1));

    return { tessGeom: tg, featGeom: fg, dotGeom: dg, posAttr: pa };
  }, [anim, tessIdx, featIdx, importance]);

  // Shader uniforms
  const wireUnis = useMemo(() => ({
    uColor: { value: MOOD.idle.color.clone() },
    uBaseOpacity: { value: 0.12 },
    uTime: { value: 0 },
    uScanY: { value: -2 },
    uIntensity: { value: 0.3 },
  }), []);

  const featUnis = useMemo(() => ({
    uColor: { value: MOOD.idle.color.clone() },
    uBaseOpacity: { value: 0.30 },
    uTime: { value: 0 },
    uScanY: { value: -2 },
    uIntensity: { value: 0.3 },
  }), []);

  const dotUnis = useMemo(() => ({
    uColor: { value: MOOD.idle.color.clone() },
    uTime: { value: 0 },
    uScanY: { value: -2 },
    uIntensity: { value: 0.3 },
    uPointSizeBase: { value: compact ? 1.5 : 2.2 },
  }), [compact]);

  // Mood change → update uniforms
  useEffect(() => {
    const cfg = MOOD[mood];
    for (const u of [wireUnis, featUnis, dotUnis]) {
      u.uColor.value.copy(cfg.color);
      u.uIntensity.value = cfg.intensity;
    }
    if (scanRef.current) {
      (scanRef.current.material as THREE.MeshBasicMaterial).color.copy(cfg.color);
    }
  }, [mood, wireUnis, featUnis, dotUnis]);

  // Per-frame animation
  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const dt = Math.min(delta, 0.05);

    // Expression animation
    animator.update(dt, t, mood);
    applyExpressions(anim, base, animator.w);

    // Breathing — chest-like motion (Y shift + subtle Z expansion)
    const breathe = Math.sin(t * 0.8) * 0.008;
    const breatheZ = Math.sin(t * 0.8 + 0.3) * 0.003;
    for (let i = 0; i < anim.length; i += 3) {
      anim[i + 1] += breathe;
      anim[i + 2] += breatheZ;
    }

    // Per-vertex organic micro-jitter for "alive" feeling
    // Uses deterministic noise based on vertex index + time
    const jitterAmt = 0.0012;
    for (let i = 0; i < anim.length; i += 3) {
      const vi = i / 3;
      // Low-frequency per-vertex noise (different phase per vertex)
      const nx = Math.sin(t * 1.1 + vi * 0.73) * Math.cos(t * 0.7 + vi * 1.17);
      const ny = Math.sin(t * 0.9 + vi * 1.31) * Math.cos(t * 1.3 + vi * 0.53);
      const nz = Math.sin(t * 0.8 + vi * 0.97) * Math.cos(t * 1.1 + vi * 0.81);
      anim[i]     += nx * jitterAmt;
      anim[i + 1] += ny * jitterAmt;
      anim[i + 2] += nz * jitterAmt * 0.5;
    }

    // Upload positions to GPU
    posAttr.needsUpdate = true;

    // Scan line sweep
    const scanY = Math.sin(t * 0.4) * 1.05;
    wireUnis.uTime.value = t;
    wireUnis.uScanY.value = scanY;
    featUnis.uTime.value = t;
    featUnis.uScanY.value = scanY;
    dotUnis.uTime.value = t;
    dotUnis.uScanY.value = scanY;
    if (scanRef.current) scanRef.current.position.y = scanY;

    // Mouse-driven face rotation + animator head micro-tilts
    mouseRef.current.lerp(targetMouse.current, 0.05);
    if (groupRef.current) {
      groupRef.current.rotation.y = mouseRef.current.x * 0.15 + Math.sin(t * 0.2) * 0.03 + animator.headTiltY;
      groupRef.current.rotation.x = -mouseRef.current.y * 0.08 + Math.cos(t * 0.15) * 0.015 + animator.headTiltX;
      // Very subtle Z rotation (head tilt side to side)
      groupRef.current.rotation.z = Math.sin(t * 0.13) * 0.012 + animator.headTiltX * 0.3;
    }
  });

  const onPointerMove = useCallback((e: ThreeEvent<PointerEvent>) => {
    targetMouse.current.set(e.point.x / 1.5, e.point.y / 1.5);
  }, []);
  const onPointerLeave = useCallback(() => { targetMouse.current.set(0, 0); }, []);

  return (
    <>
      {/* Background glow removed for clean HUD look */}

      <group ref={groupRef}>
        {/* Layer 1: Full tessellation wireframe (subtle mesh grid) */}
        <lineSegments geometry={tessGeom} frustumCulled={false}>
          <shaderMaterial
            vertexShader={wireVert}
            fragmentShader={wireFrag}
            uniforms={wireUnis}
            transparent
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </lineSegments>

        {/* Layer 2: Feature contours (eyes, lips, brows, jawline — brighter) */}
        <lineSegments geometry={featGeom} frustumCulled={false}>
          <shaderMaterial
            vertexShader={wireVert}
            fragmentShader={wireFrag}
            uniforms={featUnis}
            transparent
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </lineSegments>

        {/* Layer 3: Landmark dots */}
        <points geometry={dotGeom} frustumCulled={false}>
          <shaderMaterial
            vertexShader={dotVert}
            fragmentShader={dotFrag}
            uniforms={dotUnis}
            transparent
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </points>

        {/* Layer 4: Scan line (thin luminous plane) */}
        <mesh ref={scanRef} position={[0, 0, 0.05]}>
          <planeGeometry args={[2.4, 0.004]} />
          <meshBasicMaterial
            color={MOOD[mood].color}
            transparent
            opacity={0.25}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>

      {/* Invisible interaction plane for mouse tracking */}
      <mesh
        position={[0, 0, 0.5]}
        visible={false}
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
      >
        <planeGeometry args={[4, 4]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>
    </>
  );
}

// ─── Exported component ──────────────────────────────────────

export default function FaceMeshAvatar({ compact = false }: { compact?: boolean }) {
  const size = compact ? 'w-24 h-24' : 'w-[280px] h-[280px]';

  return (
    <div className={`${size} overflow-visible`}>
      <Canvas
        camera={{ position: [0, 0, 2.8], fov: 45 }}
        dpr={compact ? 1 : [1, 1.5]}
        gl={{
          antialias: !compact,
          alpha: true,
          powerPreference: compact ? 'low-power' : 'high-performance',
        }}
        style={{ background: 'transparent' }}
        onCreated={({ gl }) => { gl.setClearColor(0x000000, 0); }}
      >
        <FaceMeshScene compact={compact} />
      </Canvas>
    </div>
  );
}
