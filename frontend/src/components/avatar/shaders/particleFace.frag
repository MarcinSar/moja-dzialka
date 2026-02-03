/**
 * Particle Face Fragment Shader
 *
 * Renders soft glowing particles with smooth falloff
 */

precision highp float;

varying float vAlpha;
varying vec3 vColor;
varying float vDistFromCenter;

void main() {
    // Calculate distance from center of point sprite
    vec2 center = gl_PointCoord - 0.5;
    float dist = length(center);

    // Soft circular falloff with glow
    // Inner core is solid, outer edge fades smoothly
    float coreAlpha = 1.0 - smoothstep(0.0, 0.3, dist);
    float glowAlpha = 1.0 - smoothstep(0.2, 0.5, dist);

    // Combine core and glow
    float alpha = mix(glowAlpha * 0.6, coreAlpha, 0.5);

    // Discard fully transparent pixels
    if (alpha < 0.01) {
        discard;
    }

    // Apply overall alpha from vertex shader
    alpha *= vAlpha;

    // Slight fade at very edge of face for softer boundary
    float edgeFade = 1.0 - smoothstep(0.8, 1.2, vDistFromCenter);
    alpha *= edgeFade;

    // Add subtle color variation in the glow region
    vec3 glowColor = vColor * 1.2; // Slightly brighter glow
    vec3 coreColor = vColor;
    vec3 finalColor = mix(glowColor, coreColor, smoothstep(0.2, 0.35, dist));

    // Output with premultiplied alpha for additive blending
    gl_FragColor = vec4(finalColor * alpha, alpha);
}
