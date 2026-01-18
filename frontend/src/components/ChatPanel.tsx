import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { wsService } from '@/services/websocket';

export function ChatPanel() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { messages, isAgentTyping } = useChatStore();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAgentTyping]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

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
  };

  const quickActions = [
    { label: 'Blisko lasu', query: 'Szukam działki blisko lasu, cisza i spokój' },
    { label: 'Pod miastem', query: 'Działka pod Gdańskiem, dobry dojazd' },
    { label: 'Z MPZP', query: 'Działka z planem zagospodarowania, pod budowę domu' },
    { label: 'Nad wodą', query: 'Działka blisko jeziora lub rzeki' },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <h2 className="text-sm font-medium text-white flex items-center gap-2">
          <svg className="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          Asystent Działkowicz
        </h2>
        <p className="text-xs text-slate-500 mt-1">Znajdę idealną działkę dla Ciebie</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-amber-400/20 to-amber-600/20 flex items-center justify-center">
              <svg className="w-8 h-8 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                <polyline points="9 22 9 12 15 12 15 22" />
              </svg>
            </div>
            <h3 className="text-white font-medium mb-2">Witaj!</h3>
            <p className="text-sm text-slate-400 mb-6 max-w-xs mx-auto">
              Jestem Twoim asystentem w szukaniu działek na Pomorzu. Powiedz mi, czego szukasz.
            </p>

            {/* Quick actions */}
            <div className="flex flex-wrap gap-2 justify-center">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  onClick={() => setInput(action.query)}
                  className="px-3 py-1.5 text-xs bg-slate-800/50 hover:bg-slate-700/50
                           text-slate-300 rounded-full border border-slate-700/50
                           transition-colors"
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
                    message.role === 'user'
                      ? 'bg-primary text-slate-900 rounded-br-md'
                      : 'bg-slate-800/80 text-slate-100 rounded-bl-md'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  {message.isStreaming && (
                    <span className="inline-block w-1.5 h-4 bg-current animate-pulse ml-1" />
                  )}
                </div>
              </div>
            ))}

            {isAgentTyping && !messages.some((m) => m.isStreaming) && (
              <div className="flex justify-start">
                <div className="bg-slate-800/80 rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Opisz swoją wymarzoną działkę..."
            className="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl px-4 py-2.5
                     text-sm text-white placeholder-slate-500
                     focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/25
                     transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-4 py-2.5 bg-primary hover:bg-primary-hover disabled:bg-slate-700
                     disabled:text-slate-500 text-slate-900 font-medium rounded-xl
                     transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}
