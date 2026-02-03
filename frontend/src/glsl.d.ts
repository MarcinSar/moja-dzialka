/**
 * TypeScript declarations for GLSL shader imports
 * Used by vite-plugin-glsl
 */

declare module '*.glsl' {
  const value: string;
  export default value;
}

declare module '*.vert' {
  const value: string;
  export default value;
}

declare module '*.frag' {
  const value: string;
  export default value;
}

declare module '*.vs' {
  const value: string;
  export default value;
}

declare module '*.fs' {
  const value: string;
  export default value;
}
