// Face mesh wireframe vertex shader
varying float vY;
varying float vNormZ;

void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  vY = position.y;
  vNormZ = position.z;
}
