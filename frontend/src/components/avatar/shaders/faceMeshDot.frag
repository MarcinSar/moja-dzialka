// Face mesh landmark dot fragment shader
uniform vec3 uColor;
uniform float uTime;
uniform float uScanY;
uniform float uIntensity;

varying float vImportance;
varying float vY;

void main() {
  float dist = length(gl_PointCoord - vec2(0.5));
  if (dist > 0.5) discard;

  // Layered glow: bright core + soft halo (toned down)
  float core = smoothstep(0.15, 0.0, dist);
  float glow = smoothstep(0.5, 0.1, dist);
  float alpha = core * 0.7 + glow * 0.2;

  // Scale by vertex importance
  alpha *= (0.15 + vImportance * 0.85);

  // Scan line boost
  float scanDist = abs(vY - uScanY);
  float scanGlow = smoothstep(0.1, 0.0, scanDist);
  alpha += scanGlow * 0.35 * uIntensity;

  alpha = clamp(alpha, 0.0, 1.0);

  // Subtle core brightening
  vec3 color = mix(uColor, vec3(1.0), core * 0.25);

  gl_FragColor = vec4(color, alpha);
}
