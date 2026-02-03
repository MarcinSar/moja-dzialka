/**
 * Particle Face Vertex Shader
 *
 * Animates 7000 particles forming an abstract face
 * using curl noise for organic flow movement.
 */

#include "./noise.glsl"

// Uniforms
uniform float uTime;
uniform float uIntensity;      // 0.0-1.0 based on mood
uniform float uSpeed;          // Animation speed multiplier
uniform vec3 uColor;           // Mood color
uniform vec2 uMouse;           // Normalized mouse pos (-1 to 1)
uniform float uMouseRadius;    // Mouse influence radius
uniform sampler2D uTouchTrail; // Trail texture

// Instanced attributes
attribute vec3 aBasePosition;  // Face distribution position
attribute float aPhase;        // Random phase offset
attribute float aScale;        // Random scale

// Varyings to fragment shader
varying float vAlpha;
varying vec3 vColor;
varying float vDistFromCenter;

void main() {
    vec3 pos = aBasePosition;

    // Store original distance from center for fragment shader
    vDistFromCenter = length(pos.xy);

    // 1. Apply multi-layered curl noise displacement
    vec3 noisePos = pos * 2.0;
    vec3 curl1 = curlNoise(noisePos, uTime * uSpeed * 0.3);
    vec3 curl2 = curlNoise(noisePos * 2.0 + 100.0, uTime * uSpeed * 0.5) * 0.5;

    // Combine curl layers with intensity
    vec3 curlOffset = (curl1 + curl2) * 0.04 * uIntensity;
    pos += curlOffset;

    // 2. Add breathing/pulsing effect
    float breathe = sin(uTime * 0.8 + aPhase) * 0.02 * uIntensity;
    pos.z += breathe;

    // 3. Mouse interaction (repel particles)
    vec2 mouseDir = pos.xy - uMouse;
    float mouseDist = length(mouseDir);
    if (mouseDist < uMouseRadius && mouseDist > 0.001) {
        float force = (1.0 - mouseDist / uMouseRadius);
        force = force * force; // Quadratic falloff for smoother effect
        vec2 repel = normalize(mouseDir) * force * 0.15 * uIntensity;
        pos.xy += repel;
        pos.z += force * 0.05; // Slight z push on hover
    }

    // 4. Touch trail sampling for additional displacement
    vec2 trailUV = pos.xy * 0.5 + 0.5;
    trailUV = clamp(trailUV, 0.0, 1.0);
    float trailValue = texture2D(uTouchTrail, trailUV).r;
    pos.z += trailValue * 0.08;

    // 5. Eye region extra animation (thinking mode shimmer)
    float isEye = step(0.15, pos.y) * step(pos.y, 0.35) * step(abs(abs(pos.x) - 0.22), 0.15);
    pos.z += sin(uTime * 4.0 + aPhase * 2.0) * 0.01 * isEye * uIntensity;

    // 6. Mouth region extra animation (speaking mode)
    float isMouth = step(-0.45, pos.y) * step(pos.y, -0.25) * step(abs(pos.x), 0.25);
    pos.y += sin(uTime * 12.0 + pos.x * 10.0) * 0.02 * isMouth * uIntensity;

    // 7. Calculate point size with pulsing
    float pulse = sin(uTime * 2.0 + aPhase) * 0.3 * uIntensity;
    float scale = aScale * (1.0 + pulse);

    // Size varies by distance from center (larger at edges)
    float edgeFactor = smoothstep(0.3, 0.9, vDistFromCenter);
    scale *= (1.0 + edgeFactor * 0.3);

    // Transform to clip space
    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    // Point size with perspective
    gl_PointSize = scale * 400.0 / -mvPosition.z;

    // Clamp to reasonable range
    gl_PointSize = clamp(gl_PointSize, 1.0, 64.0);

    // Output varyings
    vAlpha = 0.4 + uIntensity * 0.5;

    // Color variation based on position and curl
    float colorVariation = snoise3D(pos * 3.0 + uTime * 0.2) * 0.15;
    vColor = uColor * (1.0 + colorVariation);

    // Slightly brighter at edges
    vColor *= (1.0 + edgeFactor * 0.2);
}
