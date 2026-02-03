// Face mesh landmark dot vertex shader
uniform float uTime;
uniform float uPointSizeBase;
uniform float uIntensity;

attribute float aImportance;

varying float vImportance;
varying float vY;

void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mvPosition;

  // Pulse varies per-vertex for organic feel
  float pulse = 1.0 + sin(uTime * 2.5 + position.x * 4.0 + position.y * 3.0) * 0.15 * uIntensity;
  float size = (0.3 + aImportance * 0.7) * pulse;

  // Perspective-adjusted point size
  gl_PointSize = uPointSizeBase * size * (300.0 / -mvPosition.z);
  gl_PointSize = clamp(gl_PointSize, 1.0, 24.0);

  vImportance = aImportance;
  vY = position.y;
}
