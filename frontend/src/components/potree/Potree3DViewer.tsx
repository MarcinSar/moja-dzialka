import { useEffect, useRef, useCallback, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { usePotreeStore } from '@/stores/potreeStore';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { ViewerControls } from './ViewerControls';
import { X, Maximize2, Minimize2, AlertTriangle } from 'lucide-react';

// Potree and THREE are loaded dynamically
declare global {
  interface Window {
    Potree: any;
    THREE: any;
  }
}

// Script loading state
let scriptsLoaded = false;
let scriptsLoading = false;
let loadCallbacks: ((success: boolean) => void)[] = [];

// Dynamically load Potree and Three.js scripts
async function loadPotreeScripts(): Promise<boolean> {
  // Already loaded
  if (scriptsLoaded && window.Potree && window.THREE) {
    return true;
  }

  // Currently loading - wait for it
  if (scriptsLoading) {
    return new Promise((resolve) => {
      loadCallbacks.push(resolve);
    });
  }

  scriptsLoading = true;

  const loadScript = (src: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`Failed to load: ${src}`));
      document.body.appendChild(script);
    });
  };

  try {
    // Load Three.js first (Potree depends on it)
    await loadScript('https://unpkg.com/three@0.147.0/build/three.min.js');

    // Wait a bit for THREE to be available
    await new Promise(resolve => setTimeout(resolve, 100));

    // Load Potree - using the official Potree release
    // Note: potree-core from npm has issues, use direct build instead
    await loadScript('https://unpkg.com/potree@1.8.0/build/potree/potree.js');

    scriptsLoaded = true;
    scriptsLoading = false;

    // Notify waiting callers
    loadCallbacks.forEach(cb => cb(true));
    loadCallbacks = [];

    return true;
  } catch (error) {
    console.error('Failed to load Potree scripts:', error);
    scriptsLoading = false;

    // Notify waiting callers of failure
    loadCallbacks.forEach(cb => cb(false));
    loadCallbacks = [];

    return false;
  }
}

/**
 * 3D Potree viewer for LiDAR point cloud visualization.
 *
 * Features:
 * - Point cloud rendering with color by elevation
 * - Parcel boundary overlay
 * - Orbit controls (rotate, pan, zoom)
 * - Fullscreen mode
 * - Point size and color mode controls
 *
 * Note: Potree is a complex library that requires careful integration.
 * This is a placeholder that shows loading state while scripts load.
 * Full 3D functionality will be available when backend LiDAR processing is ready.
 */
export function Potree3DViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const pointCloudRef = useRef<any>(null);

  const {
    isViewerOpen,
    potreeUrl,
    pointColorMode,
    pointSize,
    showParcelBoundary,
    closeViewer,
  } = usePotreeStore();

  const currentParcel = useParcelRevealStore((state) => state.getCurrentParcel());

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [scriptsReady, setScriptsReady] = useState(false);

  // Load scripts when viewer opens
  useEffect(() => {
    if (isViewerOpen) {
      loadPotreeScripts().then(success => {
        setScriptsReady(success);
        if (!success) {
          setLoadError('Nie udało się załadować biblioteki 3D. Funkcja będzie dostępna wkrótce.');
        }
      });
    }
  }, [isViewerOpen]);

  // Initialize Potree viewer
  const initViewer = useCallback(async () => {
    if (!containerRef.current || !potreeUrl || !scriptsReady || !window.Potree) {
      return;
    }

    setIsLoaded(false);
    setLoadError(null);

    try {
      // Create Potree viewer
      const viewer = new window.Potree.Viewer(containerRef.current);
      viewerRef.current = viewer;

      // Configure viewer
      viewer.setEDLEnabled(true);
      viewer.setFOV(60);
      viewer.setPointBudget(2_000_000);
      viewer.setBackground('gradient');

      // Set up controls
      viewer.setControls(viewer.orbitControls);

      // Build full URL for Potree data
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const fullUrl = `${apiUrl}${potreeUrl}metadata.json`;

      console.log('Loading Potree from:', fullUrl);

      // Load point cloud
      window.Potree.loadPointCloud(fullUrl, 'lidar', (e: any) => {
        if (e.pointcloud) {
          const pointcloud = e.pointcloud;
          pointCloudRef.current = pointcloud;

          viewer.scene.addPointCloud(pointcloud);

          // Set initial material properties
          pointcloud.material.size = pointSize;
          pointcloud.material.pointSizeType = window.Potree.PointSizeType.ADAPTIVE;

          // Set color mode
          updateColorMode(pointcloud, pointColorMode);

          // Fit view to point cloud
          viewer.fitToScreen();

          // Add parcel boundary if available
          if (showParcelBoundary && currentParcel?.parcel) {
            addParcelBoundary(viewer, currentParcel.parcel);
          }

          setIsLoaded(true);
          console.log('Point cloud loaded successfully');
        }
      });

    } catch (error) {
      console.error('Failed to initialize Potree viewer:', error);
      setLoadError('Nie udało się zainicjować widoku 3D');
    }
  }, [potreeUrl, pointColorMode, pointSize, showParcelBoundary, currentParcel, scriptsReady]);

  // Update color mode
  const updateColorMode = (pointcloud: any, mode: string) => {
    if (!pointcloud || !window.Potree) return;

    switch (mode) {
      case 'elevation':
        pointcloud.material.activeAttributeName = 'elevation';
        pointcloud.material.gradient = window.Potree.Gradients.SPECTRAL;
        break;
      case 'rgb':
        pointcloud.material.activeAttributeName = 'rgba';
        break;
      case 'classification':
        pointcloud.material.activeAttributeName = 'classification';
        break;
      case 'intensity':
        pointcloud.material.activeAttributeName = 'intensity';
        break;
    }
  };

  // Add parcel boundary as polygon
  const addParcelBoundary = (viewer: any, parcel: any) => {
    if (!parcel.centroid_lat || !parcel.centroid_lon) return;

    // Create a simple marker at parcel center
    // Full polygon would require geometry from backend
    const measure = new window.Potree.Measure();
    measure.closed = true;
    measure.showDistances = false;
    measure.showArea = false;
    measure.showAngles = false;

    // TODO: Get actual parcel polygon from backend
    // For now, show center point
    // const lat = parcel.centroid_lat;
    // const lon = parcel.centroid_lon;

    // Convert WGS84 to local coordinates (simplified)
    // In production, use proj4 or server-side transformation
    viewer.scene.addMeasurement(measure);
  };

  // Cleanup on unmount or close
  useEffect(() => {
    return () => {
      if (viewerRef.current) {
        // Potree viewer cleanup
        viewerRef.current.renderer?.dispose();
        viewerRef.current = null;
      }
    };
  }, []);

  // Initialize when viewer opens and scripts are ready
  useEffect(() => {
    if (isViewerOpen && potreeUrl && scriptsReady) {
      // Small delay to ensure DOM is ready
      const timer = setTimeout(initViewer, 100);
      return () => clearTimeout(timer);
    }
  }, [isViewerOpen, potreeUrl, scriptsReady, initViewer]);

  // Update point cloud settings when they change
  useEffect(() => {
    if (pointCloudRef.current) {
      pointCloudRef.current.material.size = pointSize;
      updateColorMode(pointCloudRef.current, pointColorMode);
    }
  }, [pointSize, pointColorMode]);

  // Handle fullscreen
  const toggleFullscreen = () => {
    if (!containerRef.current) return;

    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  };

  // Reset view
  const resetView = () => {
    if (viewerRef.current) {
      viewerRef.current.fitToScreen();
    }
  };

  return (
    <AnimatePresence>
      {isViewerOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-50 bg-black/90"
        >
          {/* Header */}
          <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4 bg-gradient-to-b from-black/80 to-transparent">
            <div>
              <h2 className="text-white text-xl font-semibold">
                Widok 3D terenu
              </h2>
              {currentParcel && (
                <p className="text-slate-400 text-sm">
                  {currentParcel.explanation}
                </p>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={toggleFullscreen}
                className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                aria-label={isFullscreen ? 'Wyjdź z pełnego ekranu' : 'Pełny ekran'}
              >
                {isFullscreen ? (
                  <Minimize2 className="w-5 h-5" />
                ) : (
                  <Maximize2 className="w-5 h-5" />
                )}
              </button>

              <button
                onClick={closeViewer}
                className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                aria-label="Zamknij"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>

          {/* Potree container */}
          <div
            ref={containerRef}
            className="w-full h-full"
            style={{ background: '#1a1a2e' }}
          />

          {/* Loading indicator */}
          {!isLoaded && !loadError && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-white">
                  {scriptsReady ? 'Ładuję chmurę punktów...' : 'Ładuję bibliotekę 3D...'}
                </p>
              </div>
            </div>
          )}

          {/* Error/Coming Soon message */}
          {loadError && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center bg-slate-900/90 p-8 rounded-xl max-w-md">
                <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-white mb-2">
                  Widok 3D wkrótce dostępny
                </h3>
                <p className="text-slate-400 mb-6">
                  Funkcja wizualizacji 3D terenu z danych LiDAR jest w trakcie przygotowania.
                  Już niedługo będziesz mógł zobaczyć prawdziwy teren działki w 3D!
                </p>
                <button
                  onClick={closeViewer}
                  className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium transition-colors"
                >
                  Rozumiem
                </button>
              </div>
            </div>
          )}

          {/* Controls */}
          {isLoaded && (
            <ViewerControls onResetView={resetView} />
          )}

          {/* Instructions overlay (shown briefly) */}
          <motion.div
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            transition={{ delay: 3, duration: 1 }}
            className="absolute bottom-20 left-1/2 transform -translate-x-1/2 pointer-events-none"
          >
            <div className="bg-black/70 backdrop-blur-sm px-4 py-2 rounded-lg text-sm text-slate-300">
              Przeciągnij, aby obracać | Scroll, aby przybliżyć | Shift+przeciągnij, aby przesunąć
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
