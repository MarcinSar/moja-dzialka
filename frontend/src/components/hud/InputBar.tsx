import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Send, Sparkles, Search, Brain, BookOpen, Star, UserPlus } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { wsService } from '@/services/websocket';
import { useIsMobile, useVisualViewport } from '@/hooks/useIsMobile';

// Agent type config
const AGENT_ICONS: Record<string, React.ReactNode> = {
  discovery: <Sparkles className="w-3 h-3" />,
  search: <Search className="w-3 h-3" />,
  analyst: <Brain className="w-3 h-3" />,
  narrator: <BookOpen className="w-3 h-3" />,
  feedback: <Star className="w-3 h-3" />,
  lead: <UserPlus className="w-3 h-3" />,
  orchestrator: <Sparkles className="w-3 h-3" />,
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

const SUGGESTIONS = [
  'Szukam działki w Osowej',
  'Cicha okolica pod dom',
  'Blisko morza',
];

export function InputBar() {
  const [input, setInput] = useState('');
  const [activeAgent, setActiveAgent] = useState<string>('discovery');
  const inputRef = useRef<HTMLInputElement>(null);

  const isMobile = useIsMobile();
  const { keyboardHeight } = useVisualViewport();

  const messages = useChatStore((s) => s.messages);
  const isAgentTyping = useChatStore((s) => s.isAgentTyping);
  const activities = useChatStore((s) => s.activities);
  const parcels = useParcelRevealStore((s) => s.parcels);
  const hasResults = parcels.length > 0;

  const showSuggestions = messages.length === 0;

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

  // Focus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!input.trim()) return;

      useParcelRevealStore.getState().hideReveal();

      useChatStore.getState().addMessage({
        id: `user-${Date.now()}`,
        role: 'user',
        content: input.trim(),
        timestamp: new Date(),
      });

      wsService.sendMessage(input.trim());
      setInput('');
    },
    [input]
  );

  return (
    <div
      className={`absolute z-[20] pointer-events-auto ${
        isMobile
          ? 'left-3 right-3 bottom-2 pb-safe'
          : `right-4 w-[400px] ${hasResults ? 'bottom-[200px]' : 'bottom-4'}`
      }`}
      style={isMobile && keyboardHeight > 0 ? { bottom: keyboardHeight + 8 } : undefined}
    >
      {/* Quick suggestions */}
      <AnimatePresence>
        {showSuggestions && (
          <motion.div
            className={`flex flex-wrap gap-2 mb-2 ${isMobile ? 'justify-start' : 'justify-end'}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
          >
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => setInput(suggestion)}
                className="px-3 py-2.5 md:py-1.5 rounded-full bg-slate-950/40 backdrop-blur-md
                         text-slate-400 text-xs border border-white/5
                         hover:bg-white/10 hover:text-white transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input bar */}
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <div className="flex-1 flex items-center gap-2 rounded-full backdrop-blur-xl bg-slate-900/40 border border-white/5 px-4 py-2.5
                        focus-within:border-white/10 focus-within:bg-slate-900/60 transition-all">
          {/* Agent indicator */}
          <AnimatePresence mode="wait">
            {isAgentTyping && (
              <motion.div
                key={activeAgent}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-400 shrink-0"
              >
                {AGENT_ICONS[activeAgent]}
                <span className="text-[10px]">{AGENT_LABELS[activeAgent]}</span>
              </motion.div>
            )}
          </AnimatePresence>

          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Napisz czego szukasz..."
            className="flex-1 bg-transparent text-white placeholder-slate-500
                     outline-none text-sm"
          />

          <motion.button
            type="submit"
            disabled={!input.trim()}
            className={`p-2.5 md:p-2 rounded-full transition-all shrink-0 ${
              input.trim()
                ? 'bg-amber-500 text-slate-900 hover:bg-amber-400'
                : 'bg-white/5 text-slate-600'
            }`}
            whileHover={input.trim() ? { scale: 1.05 } : {}}
            whileTap={input.trim() ? { scale: 0.95 } : {}}
          >
            <Send className="w-4 h-4" />
          </motion.button>
        </div>
      </form>
    </div>
  );
}
