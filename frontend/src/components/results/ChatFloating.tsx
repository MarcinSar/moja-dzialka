import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useChatStore } from '@/stores/chatStore';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { wsService } from '@/services/websocket';
import { Send, MessageCircle, X } from 'lucide-react';

export function ChatFloating() {
  const [input, setInput] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const messages = useChatStore((s) => s.messages);
  const isAgentTyping = useChatStore((s) => s.isAgentTyping);
  const currentStreamingId = useChatStore((s) => s.currentStreamingId);

  // Auto-scroll when messages change
  useEffect(() => {
    if (isExpanded) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isExpanded]);

  // Focus input when expanded
  useEffect(() => {
    if (isExpanded) {
      inputRef.current?.focus();
    }
  }, [isExpanded]);

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
    },
    [input]
  );

  // Last 5 messages for mini history
  const recentMessages = messages.slice(-5);
  const hasStreamingMessage = currentStreamingId !== null;

  return (
    <div className="relative">
      {/* Expanded chat history panel */}
      <AnimatePresence>
        {isExpanded && recentMessages.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="absolute bottom-full left-0 right-0 mb-3 rounded-2xl overflow-hidden
                       backdrop-blur-xl bg-slate-900/80"
            style={{
              boxShadow: '0 -8px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
            }}
          >
            {/* Close button */}
            <button
              onClick={() => setIsExpanded(false)}
              className="absolute top-2 right-2 p-1.5 rounded-lg text-slate-500 hover:text-white
                         hover:bg-white/10 transition-colors z-10"
            >
              <X className="w-4 h-4" />
            </button>

            {/* Messages */}
            <div className="p-4 max-h-[300px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700/50">
              <div className="space-y-3">
                {recentMessages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] ${
                        message.role === 'user'
                          ? 'bg-sky-500/20 text-sky-100'
                          : 'bg-white/5 text-slate-200'
                      } px-3 py-2 rounded-xl text-sm`}
                    >
                      {message.content}
                      {message.isStreaming && (
                        <motion.span
                          className="inline-block w-0.5 h-3 bg-sky-400 ml-1 align-middle"
                          animate={{ opacity: [1, 0] }}
                          transition={{ duration: 0.5, repeat: Infinity }}
                        />
                      )}
                    </div>
                  </div>
                ))}

                {/* Typing indicator */}
                {isAgentTyping && !hasStreamingMessage && (
                  <div className="flex justify-start">
                    <div className="bg-white/5 px-3 py-2 rounded-xl">
                      <div className="flex gap-1">
                        {[0, 1, 2].map((i) => (
                          <motion.div
                            key={i}
                            className="w-1.5 h-1.5 rounded-full bg-sky-400"
                            animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                            transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.1 }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input container */}
      <motion.div
        className="relative"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        {/* Glow effect on focus */}
        <motion.div
          className="absolute -inset-px rounded-full opacity-0 transition-opacity duration-300
                     bg-gradient-to-r from-sky-500/30 via-transparent to-amber-500/30"
          whileFocus={{ opacity: 1 }}
        />

        <form
          onSubmit={handleSubmit}
          className="relative flex items-center gap-3 px-5 py-3
                     rounded-full backdrop-blur-xl bg-slate-900/50"
          style={{
            boxShadow: '0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)',
          }}
        >
          {/* History toggle button */}
          {messages.length > 0 && (
            <motion.button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              className={`p-2 rounded-full transition-colors ${
                isExpanded
                  ? 'bg-sky-500/20 text-sky-400'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
              }`}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <MessageCircle className="w-5 h-5" />
            </motion.button>
          )}

          {/* Input field */}
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Zapytaj o działkę..."
            className="flex-1 bg-transparent text-white placeholder-slate-500
                       outline-none text-sm"
          />

          {/* Send button */}
          <motion.button
            type="submit"
            disabled={!input.trim()}
            className={`p-2.5 rounded-full transition-all ${
              input.trim()
                ? 'bg-amber-500/80 text-slate-900 hover:bg-amber-500'
                : 'bg-white/5 text-slate-600'
            }`}
            whileHover={input.trim() ? { scale: 1.05 } : {}}
            whileTap={input.trim() ? { scale: 0.95 } : {}}
          >
            <Send className="w-4 h-4" />
          </motion.button>
        </form>

        {/* Subtle glow underneath */}
        <div className="absolute inset-x-8 -bottom-2 h-4 bg-sky-400/10 blur-xl rounded-full" />
      </motion.div>
    </div>
  );
}
