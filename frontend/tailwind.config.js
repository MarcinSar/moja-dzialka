/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Nordic Cartographic palette
        slate: {
          850: '#1a1f2e',
          900: '#12151f',
          950: '#0a0c12',
        },
        amber: {
          400: '#fbbf24',
          500: '#f59e0b',
        },
        teal: {
          400: '#2dd4bf',
          500: '#14b8a6',
        },
        // Semantic colors
        surface: {
          DEFAULT: '#1a1f2e',
          elevated: '#242937',
          overlay: '#2e3446',
        },
        border: {
          DEFAULT: '#2e3446',
          subtle: '#232836',
        },
      },
      fontFamily: {
        display: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.65rem', { lineHeight: '1rem' }],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'pulse-subtle': 'pulseSubtle 2s ease-in-out infinite',
        'marker-drop': 'markerDrop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        markerDrop: {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      backgroundImage: {
        'contour-pattern': `url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M10 50 Q 25 30 50 50 T 90 50' fill='none' stroke='%232e3446' stroke-width='0.5'/%3E%3Cpath d='M10 70 Q 25 50 50 70 T 90 70' fill='none' stroke='%232e3446' stroke-width='0.5'/%3E%3Cpath d='M10 30 Q 25 10 50 30 T 90 30' fill='none' stroke='%232e3446' stroke-width='0.5'/%3E%3C/svg%3E")`,
        'grid-pattern': `url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0h40v40H0z' fill='none'/%3E%3Cpath d='M0 40V0h1v40zm40 0V0h-1v40zM0 0h40v1H0zm0 40h40v-1H0z' fill='%232e3446' fill-opacity='0.3'/%3E%3C/svg%3E")`,
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
      boxShadow: {
        'glow-amber': '0 0 20px rgba(251, 191, 36, 0.15)',
        'glow-teal': '0 0 20px rgba(45, 212, 191, 0.15)',
        'inner-subtle': 'inset 0 1px 0 rgba(255, 255, 255, 0.03)',
      },
    },
  },
  plugins: [],
}
