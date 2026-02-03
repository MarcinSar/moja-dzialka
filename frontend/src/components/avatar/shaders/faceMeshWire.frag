// Face mesh wireframe fragment shader
uniform vec3 uColor;
uniform float uBaseOpacity;
uniform float uTime;
uniform float uScanY;
uniform float uIntensity;

varying float vY;
varying float vNormZ;

void main() {
  // Base opacity
  float alpha = uBaseOpacity;

  // Depth fade - front of face (higher Z) is brighter
  float depthFade = smoothstep(-0.6, 0.6, vNormZ);
  alpha *= (0.4 + depthFade * 0.6);

  // Scan line glow
  float scanDist = abs(vY - uScanY);
  float scanGlow = smoothstep(0.1, 0.0, scanDist);
  alpha += scanGlow * 0.45 * uIntensity;

  // Subtle pulse
  alpha += sin(uTime * 1.5) * 0.015 * uIntensity;

  // Color whitens near scan line
  vec3 color = mix(uColor, vec3(1.0), scanGlow * 0.35);

  gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));
}
