import { useRef, useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronUp } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { useIsMobile } from '@/hooks/useIsMobile';
import { ChatBubble } from './ChatBubble';

const MAX_VISIBLE = 7;

export function ChatHud() {
  const messages = useChatStore((s) => s.messages);
  const isAgentTyping = useChatStore((s) => s.isAgentTyping);
  const currentStreamingId = useChatStore((s) => s.currentStreamingId);
  const [isExpanded, setIsExpanded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();

  // Auto-scroll when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // On mobile: tap-to-toggle. On desktop: hover.
  const [isHovered, setIsHovered] = useState(false);
  const showAll = isMobile ? isExpanded : isHovered;

  const visibleMessages = showAll ? messages : messages.slice(-MAX_VISIBLE);
  const hiddenCount = messages.length - MAX_VISIBLE;

  const toggleExpand = useCallback(() => {
    if (isMobile) setIsExpanded((v) => !v);
  }, [isMobile]);

  return (
    <motion.div
      className={`absolute flex flex-col justify-end pointer-events-none ${
        isMobile
          ? 'left-0 right-0 px-3 bottom-16 max-h-[40vh]'
          : 'right-4 bottom-20 w-[400px] max-h-[55vh]'
      }`}
      onHoverStart={isMobile ? undefined : () => setIsHovered(true)}
      onHoverEnd={isMobile ? undefined : () => setIsHovered(false)}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5, delay: 0.3 }}
    >
      {/* Mobile: "Show earlier" button */}
      {isMobile && hiddenCount > 0 && !isExpanded && (
        <button
          onClick={toggleExpand}
          className="self-center mb-2 flex items-center gap-1 px-3 py-1.5 rounded-full
                     bg-slate-950/60 backdrop-blur-sm text-slate-400 text-xs
                     pointer-events-auto border border-white/5"
        >
          <ChevronUp className="w-3 h-3" />
          <span>Pokaż wcześniejsze ({hiddenCount})</span>
        </button>
      )}

      {/* Scrollable message area */}
      <div
        className={`flex flex-col gap-2 ${
          showAll
            ? 'overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700/50 pointer-events-auto'
            : 'overflow-hidden'
        }`}
        onClick={isMobile ? toggleExpand : undefined}
      >
        <AnimatePresence mode="popLayout">
          {visibleMessages.map((message, i) => (
            <ChatBubble
              key={message.id}
              message={message}
              index={i}
              totalVisible={visibleMessages.length}
              isHovered={showAll}
            />
          ))}
        </AnimatePresence>

        {/* Typing indicator */}
        {isAgentTyping && !currentStreamingId && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex justify-start pointer-events-auto"
          >
            <div className="bg-slate-950/60 backdrop-blur-sm px-4 py-2.5 rounded-xl border-l-2 border-cyan-400/40">
              <div className="flex gap-1.5">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-cyan-400"
                    animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                    transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}

        <div ref={bottomRef} />
      </div>
    </motion.div>
  );
}
