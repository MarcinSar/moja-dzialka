import { motion } from 'motion/react';
import { AvatarCompact } from '../avatar/AvatarCompact';
import { ResultsChat } from '../chat/ResultsChat';
import { MapPanel } from '../MapPanel';
import { ActivityPanel } from '../ActivityPanel';
import { Header } from '../Header';

interface ResultsPhaseProps {
  stats: { total_parcels: number; total_gminy: number } | null;
}

export function ResultsPhase({ stats }: ResultsPhaseProps) {
  return (
    <motion.div
      className="h-screen flex flex-col bg-surface"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <Header stats={stats} />

      {/* Main content - 3 panel layout */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left panel - Chat with compact avatar */}
        <motion.div
          className="w-[30%] min-w-[320px] border-r border-border bg-surface-elevated/30 flex flex-col"
          initial={{ x: -50, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          {/* Avatar header */}
          <div className="p-4 border-b border-border flex items-center gap-3">
            <AvatarCompact />
            <div>
              <h2 className="text-sm font-medium text-white">Asystent Działkowicz</h2>
              <p className="text-xs text-slate-500">Znajdę idealną działkę</p>
            </div>
          </div>

          {/* Chat messages */}
          <div className="flex-1 overflow-hidden">
            <ResultsChat />
          </div>
        </motion.div>

        {/* Center panel - Map */}
        <motion.div
          className="flex-1 flex flex-col bg-surface"
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <MapPanel />
        </motion.div>

        {/* Right panel - Activity */}
        <motion.div
          className="w-[20%] min-w-[240px] border-l border-border bg-surface-elevated/30"
          initial={{ x: 50, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <ActivityPanel />
        </motion.div>
      </main>
    </motion.div>
  );
}
