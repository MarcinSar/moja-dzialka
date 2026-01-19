import { motion, AnimatePresence } from 'framer-motion';
import { usePotreeStore, isLoading } from '@/stores/potreeStore';
import { Mountain, X } from 'lucide-react';

/**
 * Loading overlay for LiDAR data processing.
 *
 * Shows animated progress while downloading and converting LiDAR data.
 * Displays: 3D terrain icon, progress bar, status message.
 */
export function LidarLoadingOverlay() {
  const {
    loadingStatus,
    loadingProgress,
    loadingMessage,
    errorMessage,
    cancelLoading,
  } = usePotreeStore();

  const isVisible = isLoading() || loadingStatus === 'error';

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl border border-slate-700"
          >
            {/* Close button */}
            <button
              onClick={cancelLoading}
              className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors"
              aria-label="Anuluj"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Animated 3D icon */}
            <div className="flex justify-center mb-6">
              <motion.div
                animate={{
                  rotateY: [0, 360],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: 'linear',
                }}
                style={{ transformStyle: 'preserve-3d' }}
                className="relative"
              >
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                  <Mountain className="w-10 h-10 text-white" />
                </div>

                {/* Floating particles effect */}
                {[...Array(6)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="absolute w-2 h-2 rounded-full bg-emerald-400"
                    initial={{
                      x: 0,
                      y: 0,
                      opacity: 0,
                    }}
                    animate={{
                      x: [0, (i % 2 === 0 ? 1 : -1) * (20 + i * 10)],
                      y: [0, -30 - i * 5],
                      opacity: [0, 1, 0],
                    }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      delay: i * 0.2,
                      ease: 'easeOut',
                    }}
                    style={{
                      left: '50%',
                      top: '50%',
                    }}
                  />
                ))}
              </motion.div>
            </div>

            {/* Title */}
            <h3 className="text-xl font-semibold text-white text-center mb-2">
              {loadingStatus === 'error' ? 'Błąd' : 'Ładuję teren 3D'}
            </h3>

            {/* Status message */}
            <p className="text-slate-300 text-center mb-6 min-h-[1.5rem]">
              {loadingMessage || 'Przygotowuję wizualizację...'}
            </p>

            {/* Progress bar */}
            {loadingStatus !== 'error' && (
              <div className="relative">
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${loadingProgress}%` }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                  />
                </div>

                {/* Progress percentage */}
                <div className="flex justify-between mt-2 text-sm">
                  <span className="text-slate-400">
                    {loadingProgress < 70 ? 'Pobieranie' : 'Konwersja'}
                  </span>
                  <span className="text-emerald-400 font-medium">
                    {Math.round(loadingProgress)}%
                  </span>
                </div>
              </div>
            )}

            {/* Error state */}
            {loadingStatus === 'error' && (
              <div className="text-center">
                <p className="text-red-400 mb-4">{errorMessage}</p>
                <button
                  onClick={cancelLoading}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  Zamknij
                </button>
              </div>
            )}

            {/* Info text */}
            {loadingStatus !== 'error' && (
              <p className="text-xs text-slate-500 text-center mt-4">
                Dane LiDAR z GUGiK. Pierwszy raz może potrwać do 90 sekund.
              </p>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
