import { motion, AnimatePresence } from 'motion/react';
import { useChat } from '@/hooks/useChat';
import { useEffect, useRef } from 'react';

// Minimal streaming cursor
function StreamingCursor() {
  return (
    <motion.span
      className="inline-block w-0.5 h-4 bg-cyan-400 ml-1 align-middle"
      animate={{ opacity: [1, 0] }}
      transition={{ duration: 0.5, repeat: Infinity }}
    />
  );
}

// Single message - minimal, floating style
function Message({ message, isLast }: { message: { id: string; role: string; content: string; isStreaming?: boolean }; isLast: boolean }) {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, filter: 'blur(10px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`max-w-[85%] ${isUser ? 'text-right' : 'text-left'}`}>
        {/* Role indicator - subtle */}
        <motion.span
          className={`text-[10px] uppercase tracking-widest mb-1 block ${
            isUser ? 'text-slate-500' : 'text-cyan-400/70'
          }`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.7 }}
        >
          {isUser ? 'Ty' : 'AI'}
        </motion.span>

        {/* Message text - clean, no box */}
        <p className={`text-base leading-relaxed ${
          isUser ? 'text-slate-300' : 'text-white'
        }`}>
          {message.content}
          {message.isStreaming && <StreamingCursor />}
        </p>

        {/* Subtle underline for assistant messages */}
        {!isUser && isLast && (
          <motion.div
            className="h-px bg-gradient-to-r from-cyan-400/50 via-cyan-400/20 to-transparent mt-2"
            initial={{ scaleX: 0, originX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          />
        )}
      </div>
    </motion.div>
  );
}

// Typing indicator - minimal dots
function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex items-center gap-3"
    >
      <span className="text-[10px] uppercase tracking-widest text-cyan-400/70">AI</span>
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-cyan-400"
            animate={{ opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.1 }}
          />
        ))}
      </div>
    </motion.div>
  );
}

export function DiscoveryChat() {
  const { input, setInput, messages, isAgentTyping, messagesEndRef, handleSubmit } = useChat();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const hasMessages = messages.length > 0;
  const hasStreamingMessage = messages.some(m => m.isStreaming);

  return (
    <div className="w-full">
      {/* Messages - minimal, floating */}
      <AnimatePresence mode="popLayout">
        {hasMessages && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-8 space-y-6 max-h-[40vh] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700/50 scrollbar-track-transparent"
          >
            {messages.map((message, index) => (
              <Message
                key={message.id}
                message={message}
                isLast={index === messages.length - 1 && message.role === 'assistant'}
              />
            ))}

            <AnimatePresence>
              {isAgentTyping && !hasStreamingMessage && (
                <TypingIndicator />
              )}
            </AnimatePresence>

            <div ref={messagesEndRef} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input - clean, minimal */}
      <motion.form
        onSubmit={handleSubmit}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        <div className="relative">
          {/* Subtle glow under input */}
          <div className="absolute -inset-1 bg-gradient-to-r from-cyan-400/10 via-transparent to-blue-500/10 rounded-2xl blur-xl" />

          <div className="relative flex items-center gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={hasMessages ? "Powiedz więcej..." : "Opisz swoją wymarzoną działkę..."}
              className="flex-1 bg-transparent border-0 border-b border-slate-700/30 focus:border-cyan-400/40
                       px-0 py-3 text-lg text-white placeholder-slate-500
                       outline-none ring-0 focus:ring-0 focus:outline-none transition-colors"
              style={{ boxShadow: 'none' }}
            />

            <motion.button
              type="submit"
              disabled={!input.trim()}
              className="text-cyan-400 disabled:text-slate-600 transition-colors p-2"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </motion.button>
          </div>
        </div>
      </motion.form>
    </div>
  );
}
