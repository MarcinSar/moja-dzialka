import { create } from 'zustand';

/**
 * Potree viewer state management.
 *
 * Handles LiDAR loading progress and 3D viewer display.
 */

export type LoadingStatus = 'idle' | 'pending' | 'downloading' | 'converting' | 'ready' | 'error';

export type PointColorMode = 'elevation' | 'rgb' | 'classification' | 'intensity';

export interface PotreeState {
  // Loading state
  loadingStatus: LoadingStatus;
  loadingProgress: number;        // 0-100
  loadingMessage: string;
  jobId: string | null;

  // Viewer state
  isViewerOpen: boolean;
  potreeUrl: string | null;
  parcelId: string | null;
  tileId: string | null;

  // Viewer settings
  pointColorMode: PointColorMode;
  pointSize: number;              // 1-5
  showParcelBoundary: boolean;

  // Error state
  errorMessage: string | null;

  // Actions - Loading
  startLoading: (parcelId: string, jobId: string) => void;
  updateProgress: (progress: number, message: string, status?: LoadingStatus) => void;
  setReady: (potreeUrl: string, tileId: string) => void;
  setError: (message: string) => void;
  cancelLoading: () => void;

  // Actions - Viewer
  openViewer: () => void;
  closeViewer: () => void;

  // Actions - Settings
  setPointColorMode: (mode: PointColorMode) => void;
  setPointSize: (size: number) => void;
  toggleParcelBoundary: () => void;

  // Reset
  reset: () => void;
}

const initialState = {
  loadingStatus: 'idle' as LoadingStatus,
  loadingProgress: 0,
  loadingMessage: '',
  jobId: null,
  isViewerOpen: false,
  potreeUrl: null,
  parcelId: null,
  tileId: null,
  pointColorMode: 'elevation' as PointColorMode,
  pointSize: 2,
  showParcelBoundary: true,
  errorMessage: null,
};

export const usePotreeStore = create<PotreeState>((set, get) => ({
  ...initialState,

  // Loading actions
  startLoading: (parcelId, jobId) => set({
    loadingStatus: 'pending',
    loadingProgress: 0,
    loadingMessage: 'Przygotowuję dane LiDAR...',
    jobId,
    parcelId,
    errorMessage: null,
  }),

  updateProgress: (progress, message, status) => set((state) => ({
    loadingProgress: progress,
    loadingMessage: message,
    loadingStatus: status || (progress < 70 ? 'downloading' : 'converting'),
  })),

  setReady: (potreeUrl, tileId) => set({
    loadingStatus: 'ready',
    loadingProgress: 100,
    loadingMessage: 'Gotowe!',
    potreeUrl,
    tileId,
    isViewerOpen: true,  // Auto-open viewer when ready
  }),

  setError: (message) => set({
    loadingStatus: 'error',
    errorMessage: message,
    loadingProgress: 0,
    loadingMessage: message,
  }),

  cancelLoading: () => set({
    loadingStatus: 'idle',
    loadingProgress: 0,
    loadingMessage: '',
    jobId: null,
  }),

  // Viewer actions
  openViewer: () => {
    const state = get();
    if (state.potreeUrl) {
      set({ isViewerOpen: true });
    }
  },

  closeViewer: () => set({ isViewerOpen: false }),

  // Settings actions
  setPointColorMode: (mode) => set({ pointColorMode: mode }),

  setPointSize: (size) => set({ pointSize: Math.max(1, Math.min(5, size)) }),

  toggleParcelBoundary: () => set((state) => ({
    showParcelBoundary: !state.showParcelBoundary,
  })),

  // Reset
  reset: () => set(initialState),
}));

/**
 * Check if viewer can be opened (has valid Potree URL).
 */
export function canOpenViewer(): boolean {
  return usePotreeStore.getState().potreeUrl !== null;
}

/**
 * Check if currently loading LiDAR data.
 */
export function isLoading(): boolean {
  const status = usePotreeStore.getState().loadingStatus;
  return ['pending', 'downloading', 'converting'].includes(status);
}
