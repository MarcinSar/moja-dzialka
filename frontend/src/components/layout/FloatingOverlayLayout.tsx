/**
 * FloatingOverlayLayout - Unified layout with full-screen map and floating panels
 *
 * Features:
 * - Full-screen map as the base layer (always visible)
 * - Floating chat panel with integrated avatar (minimizable/maximizable)
 * - Property cards strip at bottom
 * - Agent indicators showing which sub-agent is active
 * - Responsive design with mobile bottom sheet fallback
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { useChatStore } from '@/stores/chatStore';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { wsService } from '@/services/websocket';
import { MapPanelImmersive } from '../results/MapPanelImmersive';
import { ParticleBackground } from '../effects/ParticleBackground';
import { Avatar } from '../avatar/Avatar';
import { PropertyCardsStrip } from '../results/PropertyCardsStrip';
import { ParcelDetailsPanel } from '../results/ParcelDetailsPanel';
import {
  Send,
  MessageCircle,
  ChevronDown,
  ChevronUp,
  Minimize2,
  Maximize2,
  Sparkles,
  Search,
  Brain,
  BookOpen,
  Star,
  UserPlus,
} from 'lucide-react';

type ChatPanelState = 'minimized' | 'compact' | 'expanded';

// Agent type icons for multi-agent system
const AGENT_ICONS: Record<string, React.ReactNode> = {
  discovery: <Sparkles className="w-3.5 h-3.5" />,
  search: <Search className="w-3.5 h-3.5" />,
  analyst: <Brain className="w-3.5 h-3.5" />,
  narrator: <BookOpen className="w-3.5 h-3.5" />,
  feedback: <Star className="w-3.5 h-3.5" />,
  lead: <UserPlus className="w-3.5 h-3.5" />,
  orchestrator: <Sparkles className="w-3.5 h-3.5" />,
};

const AGENT_LABELS: Record<string, string> = {
  discovery: 'Odkrywca',
  search: 'Poszukiwacz',
  analyst: 'Analityk',
  narrator: 'Narrator',
  feedback: 'Feedback',
  lead: 'Kontakt',
  orchestrator: 'Koordynator',
};

export function FloatingOverlayLayout() {
  const phase = useUIPhaseStore((s) => s.phase);
  const avatarMood = useUIPhaseStore((s) => s.avatarMood);
  const transitionToDiscovery = useUIPhaseStore((s) => s.transitionToDiscovery);

  const messages = useChatStore((s) => s.messages);
  const isAgentTyping = useChatStore((s) => s.isAgentTyping);
  const currentStreamingId = useChatStore((s) => s.currentStreamingId);
  const activities = useChatStore((s) => s.activities);

  const parcels = useParcelRevealStore((s) => s.parcels);

  const [chatState, setChatState] = useState<ChatPanelState>('expanded');
  const [input, setInput] = useState('');
  const [activeAgent, setActiveAgent] = useState<string>('discovery');
  const [isMobile, setIsMobile] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check if mobile
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Extract active agent from activities
  useEffect(() => {
    const lastSkillActivity = activities
      .filter((a) => a.message?.startsWith('Faza:'))
      .pop();
    if (lastSkillActivity?.details) {
      const match = lastSkillActivity.details.match(/Skill: (\w+)/);
      if (match) {
        const skillToAgent: Record<string, string> = {
          discovery: 'discovery',
          search: 'search',
          evaluation: 'analyst',
          narrator: 'narrator',
          market_analysis: 'analyst',
          lead_capture: 'lead',
        };
        setActiveAgent(skillToAgent[match[1]] || 'orchestrator');
      }
    }
  }, [activities]);

  // Auto-scroll messages
  useEffect(() => {
    if (chatState !== 'minimized') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, chatState]);

  // Focus input when expanded
  useEffect(() => {
    if (chatState === 'expanded' && !isMobile) {
      inputRef.current?.focus();
    }
  }, [chatState, isMobile]);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!input.trim()) return;

      // Hide parcel reveal if visible
      useParcelRevealStore.getState().hideReveal();

      // Add user message
      useChatStore.getState().addMessage({
        id: `user-${Date.now()}`,
        role: 'user',
        content: input.trim(),
        timestamp: new Date(),
      });

      // Send via WebSocket
      wsService.sendMessage(input.trim());
      setInput('');

      // Expand chat to see response
      if (chatState === 'minimized') {
        setChatState('compact');
      }
    },
    [input, chatState]
  );

  const toggleChatState = () => {
    if (chatState === 'minimized') {
      setChatState('compact');
    } else if (chatState === 'compact') {
      setChatState('expanded');
    } else {
      setChatState('compact');
    }
  };

  const hasMessages = messages.length > 0;
  const hasResults = parcels.length > 0;
  const showIntro = phase === 'discovery' && !hasMessages;

  return (
    <div className="h-screen w-screen relative overflow-hidden bg-slate-950">
      {/* Layer 1: Particle Background (always visible, underneath everything) */}
      <ParticleBackground />

      {/* Layer 2: Gradient overlays */}
      <div className="absolute inset-0 bg-gradient-radial from-sky-500/5 via-transparent to-transparent pointer-events-none z-[1]" />

      {/* Layer 3: Full-screen Map */}
      <motion.div
        className="absolute inset-0 z-[2]"
        initial={{ opacity: 0 }}
        animate={{ opacity: hasMessages ? 1 : 0.3 }}
        transition={{ duration: 0.8 }}
      >
        <MapPanelImmersive />
      </motion.div>

      {/* Layer 4: Map fade edges */}
      <div className="absolute inset-0 pointer-events-none z-[3]">
        <div className="absolute top-0 inset-x-0 h-24 bg-gradient-to-b from-slate-950 to-transparent" />
        <div className="absolute bottom-0 inset-x-0 h-48 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent" />
        <div className="absolute left-0 inset-y-0 w-8 bg-gradient-to-r from-slate-950/30 to-transparent" />
        <div className="absolute right-0 inset-y-0 w-8 bg-gradient-to-l from-slate-950/30 to-transparent" />
      </div>

      {/* Layer 5: Logo */}
      <motion.div
        className="absolute top-4 left-4 z-50 flex items-center gap-2"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center">
          <svg
            className="w-4 h-4 text-white"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
        </div>
        <span className="text-white font-medium text-sm">moja-działka</span>
      </motion.div>

      {/* Layer 6: Back button (when results visible) */}
      <AnimatePresence>
        {hasResults && (
          <motion.button
            onClick={transitionToDiscovery}
            className="absolute top-4 right-4 z-50 flex items-center gap-2 px-3 py-2 rounded-xl
                       backdrop-blur-xl bg-slate-900/40 text-slate-400 hover:text-white
                       transition-colors group"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            whileHover={{ scale: 1.02 }}
          >
            <svg
              className="w-4 h-4 transition-transform group-hover:-translate-x-1"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            <span className="text-sm">Nowe wyszukiwanie</span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Layer 7: Avatar — always visible, repositions smoothly */}
      <motion.div
        className="absolute z-[10] pointer-events-none"
        animate={
          showIntro
            ? {
                top: '50%',
                left: '50%',
                x: '-50%',
                y: '-55%',
                scale: 1,
              }
            : isMobile
            ? {
                top: '12px',
                left: '50%',
                x: '-50%',
                y: '0%',
                scale: 0.45,
              }
            : {
                top: '50%',
                left: hasResults ? '28%' : '36%',
                x: '-50%',
                y: '-50%',
                scale: 0.55,
              }
        }
        transition={{ type: 'spring', damping: 28, stiffness: 120, mass: 1 }}
      >
        <Avatar variant="full" />
      </motion.div>

      {/* Intro text — only before first message */}
      <AnimatePresence>
        {showIntro && (
          <motion.div
            className="absolute inset-x-0 z-[10] flex justify-center pointer-events-none"
            style={{ top: '62%' }}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 10, opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <div className="text-center space-y-2">
              <h1 className="text-2xl font-semibold text-white">
                Znajdź swoją wymarzoną działkę
              </h1>
              <p className="text-slate-400 max-w-md mx-auto">
                Powiedz mi, czego szukasz - lokalizacja, cisza, natura, dostępność.
                Przeszukam tysiące działek i znajdę idealne dla Ciebie.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Layer 8: Property Cards Strip (when results visible) */}
      <AnimatePresence>
        {hasResults && chatState !== 'expanded' && (
          <motion.div
            className="absolute bottom-32 left-1/2 -translate-x-1/2 z-30 w-full max-w-5xl px-4"
            initial={{ y: 60, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 60, opacity: 0 }}
            transition={{ type: 'spring', damping: 25 }}
          >
            <PropertyCardsStrip />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Layer 9: Results count badge */}
      <AnimatePresence>
        {hasResults && chatState !== 'expanded' && (
          <motion.div
            className="absolute bottom-[260px] left-1/2 -translate-x-1/2 z-30"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <div className="flex items-center gap-2 px-4 py-2 rounded-full backdrop-blur-xl bg-slate-900/50">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              <span className="text-sm text-slate-300">
                Znaleziono{' '}
                <span className="text-amber-400 font-medium">{parcels.length}</span> działek
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Layer 10: Floating Chat Panel */}
      <motion.div
        className={`absolute z-40 ${
          isMobile
            ? 'inset-x-0 bottom-0'
            : chatState === 'expanded'
            ? 'right-4 bottom-4 top-20 w-[420px]'
            : 'right-4 bottom-4 w-[380px]'
        }`}
        layout
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      >
        <motion.div
          className={`h-full flex flex-col rounded-2xl overflow-hidden
                     backdrop-blur-2xl bg-slate-900/70 border border-white/10
                     shadow-2xl shadow-black/30 ${
                       isMobile && chatState === 'minimized' ? 'rounded-b-none' : ''
                     }`}
          style={{
            boxShadow:
              '0 25px 50px -12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1)',
          }}
        >
          {/* Chat Header with Avatar */}
          <div
            className="flex items-center justify-between px-4 py-3 border-b border-white/5 cursor-pointer select-none"
            onClick={toggleChatState}
          >
            <div className="flex items-center gap-3">
              {/* Status indicator dot */}
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/10 to-blue-500/10
                             flex items-center justify-center">
                <motion.div
                  className="w-3 h-3 rounded-full bg-cyan-400"
                  animate={{
                    scale: avatarMood === 'speaking' ? [1, 1.3, 1] : avatarMood === 'thinking' ? [1, 1.15, 1] : 1,
                    opacity: avatarMood === 'idle' ? 0.6 : 1,
                  }}
                  transition={{
                    duration: avatarMood === 'speaking' ? 0.4 : 1.5,
                    repeat: avatarMood !== 'idle' ? Infinity : 0,
                  }}
                />
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white">Parcela</span>
                  {/* Agent indicator */}
                  <AnimatePresence mode="wait">
                    {isAgentTyping && (
                      <motion.div
                        key={activeAgent}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-400"
                      >
                        {AGENT_ICONS[activeAgent]}
                        <span className="text-xs">{AGENT_LABELS[activeAgent]}</span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
                <span className="text-xs text-slate-500">
                  {isAgentTyping
                    ? 'pisze...'
                    : avatarMood === 'thinking'
                    ? 'myśli...'
                    : 'Twój doradca nieruchomości'}
                </span>
              </div>
            </div>

            {/* Expand/Collapse buttons */}
            <div className="flex items-center gap-1">
              {chatState !== 'minimized' && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setChatState('minimized');
                  }}
                  className="p-2 rounded-lg text-slate-500 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <Minimize2 className="w-4 h-4" />
                </button>
              )}
              {chatState === 'minimized' && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setChatState('expanded');
                  }}
                  className="p-2 rounded-lg text-slate-500 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  toggleChatState();
                }}
                className="p-2 rounded-lg text-slate-500 hover:text-white hover:bg-white/10 transition-colors"
              >
                {chatState === 'expanded' ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronUp className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Messages Area */}
          <AnimatePresence>
            {chatState !== 'minimized' && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{
                  height: chatState === 'expanded' ? 'auto' : 200,
                  opacity: 1,
                }}
                exit={{ height: 0, opacity: 0 }}
                className="flex-1 overflow-hidden"
              >
                <div
                  className={`h-full overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-slate-700/50 ${
                    chatState === 'expanded' ? 'max-h-[calc(100vh-280px)]' : 'max-h-[200px]'
                  }`}
                >
                  {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-8">
                      <div className="w-12 h-12 rounded-xl bg-slate-800/50 flex items-center justify-center mb-3">
                        <MessageCircle className="w-6 h-6 text-slate-500" />
                      </div>
                      <p className="text-slate-400 text-sm max-w-[240px]">
                        Powiedz czego szukasz - np. "spokojna działka w Osowej, blisko lasu"
                      </p>
                    </div>
                  ) : (
                    messages.map((message) => (
                      <motion.div
                        key={message.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[85%] ${
                            message.role === 'user'
                              ? 'bg-sky-500/20 text-sky-100 rounded-2xl rounded-br-md'
                              : 'bg-white/5 text-slate-200 rounded-2xl rounded-bl-md'
                          } px-4 py-2.5 text-sm leading-relaxed`}
                        >
                          {message.content}
                          {message.isStreaming && (
                            <motion.span
                              className="inline-block w-0.5 h-4 bg-sky-400 ml-1 align-middle"
                              animate={{ opacity: [1, 0] }}
                              transition={{ duration: 0.5, repeat: Infinity }}
                            />
                          )}
                        </div>
                      </motion.div>
                    ))
                  )}

                  {/* Typing indicator */}
                  {isAgentTyping && !currentStreamingId && (
                    <div className="flex justify-start">
                      <div className="bg-white/5 px-4 py-2.5 rounded-2xl rounded-bl-md">
                        <div className="flex gap-1.5">
                          {[0, 1, 2].map((i) => (
                            <motion.div
                              key={i}
                              className="w-2 h-2 rounded-full bg-sky-400"
                              animate={{ opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
                              transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Input Area */}
          <div className="p-3 border-t border-white/5">
            <form onSubmit={handleSubmit} className="flex items-center gap-2">
              <div className="flex-1 relative">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Napisz wiadomość..."
                  className="w-full px-4 py-2.5 rounded-xl bg-white/5 text-white placeholder-slate-500
                           outline-none text-sm transition-colors
                           focus:bg-white/10 focus:ring-1 focus:ring-sky-500/50"
                />
              </div>
              <motion.button
                type="submit"
                disabled={!input.trim()}
                className={`p-2.5 rounded-xl transition-all ${
                  input.trim()
                    ? 'bg-amber-500 text-slate-900 hover:bg-amber-400'
                    : 'bg-white/5 text-slate-600'
                }`}
                whileHover={input.trim() ? { scale: 1.05 } : {}}
                whileTap={input.trim() ? { scale: 0.95 } : {}}
              >
                <Send className="w-4 h-4" />
              </motion.button>
            </form>

            {/* Quick suggestions */}
            {messages.length === 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {[
                  'Szukam działki w Osowej',
                  'Cicha okolica pod dom',
                  'Blisko morza',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="px-3 py-1.5 rounded-lg bg-white/5 text-slate-400 text-xs
                             hover:bg-white/10 hover:text-white transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>

      {/* Layer 11: Parcel Details Panel (modal) */}
      <ParcelDetailsPanel />
    </div>
  );
}
