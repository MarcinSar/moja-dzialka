import { useChat } from '@/hooks/useChat';

export function ResultsChat() {
  const { input, setInput, messages, isAgentTyping, messagesEndRef, handleSubmit } = useChat();

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
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
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Powiedz więcej..."
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
