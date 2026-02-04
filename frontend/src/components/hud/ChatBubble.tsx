import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import type { ChatMessage } from '@/types';

interface ChatBubbleProps {
  message: ChatMessage;
  index: number;
  totalVisible: number;
  isHovered: boolean;
}

const FADE_DELAY_MS = 30000; // 30s before starting fade

export function ChatBubble({ message, index, totalVisible, isHovered }: ChatBubbleProps) {
  const [age, setAge] = useState(0);

  // Track message age for auto-fade
  useEffect(() => {
    const interval = setInterval(() => {
      setAge(Date.now() - message.timestamp.getTime());
    }, 5000);
    return () => clearInterval(interval);
  }, [message.timestamp]);

  const isUser = message.role === 'user';
  const isFaded = !isHovered && age > FADE_DELAY_MS && !message.isStreaming;
  // Older messages get more transparent
  const positionOpacity = isHovered ? 1 : Math.max(0.4, 1 - (totalVisible - 1 - index) * 0.15);
  const fadeOpacity = isFaded ? 0.3 : positionOpacity;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, filter: 'blur(4px)' }}
      animate={{
        opacity: fadeOpacity,
        y: 0,
        filter: 'blur(0px)',
      }}
      exit={{ opacity: 0, y: -10, filter: 'blur(4px)' }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} pointer-events-auto`}
    >
      <div
        className={`max-w-[92%] md:max-w-[85%] px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? 'bg-sky-500/15 text-sky-100 rounded-xl border-l-2 border-sky-400/40 ml-4 md:ml-8'
            : 'bg-slate-950/60 backdrop-blur-sm text-slate-200 rounded-xl border-l-2 border-cyan-400/40'
        }`}
      >
        {message.content}
        {message.isStreaming && (
          <motion.span
            className="inline-block w-0.5 h-4 bg-cyan-400 ml-1 align-middle"
            animate={{ opacity: [1, 0] }}
            transition={{ duration: 0.5, repeat: Infinity }}
          />
        )}
      </div>
    </motion.div>
  );
}
