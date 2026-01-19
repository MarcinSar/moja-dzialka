import type { Variants, Transition } from 'motion/react';

// Animation variants for different avatar moods
export const avatarVariants: Variants = {
  idle: {
    scale: 1,
    rotate: 0,
    opacity: 1,
  },
  thinking: {
    scale: [1, 0.95, 1],
    rotate: [0, 5, -5, 0],
    opacity: 1,
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  speaking: {
    scale: [1, 1.03, 1, 1.02, 1],
    opacity: 1,
    transition: {
      duration: 0.8,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  excited: {
    scale: [1, 1.1, 1],
    rotate: [0, 0, 0],
    opacity: 1,
    transition: {
      duration: 0.5,
      ease: 'easeOut',
    },
  },
};

// Pulse animation for the glow ring
export const ringVariants: Variants = {
  idle: {
    opacity: [0.3, 0.5, 0.3],
    scale: [1, 1.05, 1],
    transition: {
      duration: 3,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  thinking: {
    opacity: [0.5, 0.8, 0.5],
    scale: [1, 1.1, 1],
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  speaking: {
    opacity: [0.4, 0.7, 0.4],
    scale: [1, 1.08, 1],
    transition: {
      duration: 0.6,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  excited: {
    opacity: 0.9,
    scale: 1.15,
    transition: {
      duration: 0.3,
      ease: 'easeOut',
    },
  },
};

// Inner icon animation
export const iconVariants: Variants = {
  idle: {
    y: 0,
    scale: 1,
  },
  thinking: {
    y: [-2, 2, -2],
    scale: 0.95,
    transition: {
      y: {
        duration: 1,
        repeat: Infinity,
        ease: 'easeInOut',
      },
    },
  },
  speaking: {
    y: 0,
    scale: [1, 1.05, 1],
    transition: {
      scale: {
        duration: 0.4,
        repeat: Infinity,
        ease: 'easeInOut',
      },
    },
  },
  excited: {
    y: [-5, 0],
    scale: 1.1,
    transition: {
      duration: 0.4,
      ease: 'easeOut',
    },
  },
};

// Shared transition config for smooth mood changes
export const moodTransition: Transition = {
  duration: 0.4,
  ease: 'easeInOut',
};

// Avatar size configurations
export const avatarSizes = {
  full: {
    container: 'w-48 h-48',
    ring: 'w-56 h-56',
    icon: 'w-16 h-16',
  },
  compact: {
    container: 'w-12 h-12',
    ring: 'w-14 h-14',
    icon: 'w-5 h-5',
  },
} as const;
