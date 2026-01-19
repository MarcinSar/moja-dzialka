import { useState, useRef, useEffect, useCallback } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { wsService } from '@/services/websocket';

export const quickActions = [
  { label: 'Blisko lasu', query: 'Szukam działki blisko lasu, cisza i spokój' },
  { label: 'Pod miastem', query: 'Działka pod Gdańskiem, dobry dojazd' },
  { label: 'Z MPZP', query: 'Działka z planem zagospodarowania, pod budowę domu' },
  { label: 'Nad wodą', query: 'Działka blisko jeziora lub rzeki' },
];

export function useChat() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { messages, isAgentTyping } = useChatStore();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAgentTyping]);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!input.trim()) return;

      // Hide parcel reveal card when user sends a new message
      useParcelRevealStore.getState().hideReveal();

      // Add user message to store
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

  const sendMessage = useCallback((content: string) => {
    // Hide parcel reveal card when user sends a new message
    useParcelRevealStore.getState().hideReveal();

    useChatStore.getState().addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    });
    wsService.sendMessage(content.trim());
  }, []);

  return {
    input,
    setInput,
    messages,
    isAgentTyping,
    messagesEndRef,
    handleSubmit,
    sendMessage,
    quickActions,
  };
}
