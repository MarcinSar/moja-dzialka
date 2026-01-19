import { create } from 'zustand';
import type { ChatMessage, AgentActivity } from '@/types';

interface ChatState {
  // Chat state
  messages: ChatMessage[];
  activities: AgentActivity[];
  isConnected: boolean;
  isAgentTyping: boolean;
  connectionError: string | null;
  currentStreamingId: string | null;

  // Session
  sessionId: string | null;

  // Actions
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, content: string, isComplete?: boolean) => void;
  appendToLastMessage: (content: string) => void;
  startStreaming: (id: string, initialContent: string) => void;
  finishStreaming: () => void;
  addActivity: (activity: AgentActivity) => void;
  updateActivity: (id: string, updates: Partial<AgentActivity>) => void;
  setConnected: (connected: boolean) => void;
  setAgentTyping: (typing: boolean) => void;
  setConnectionError: (error: string | null) => void;
  setSessionId: (id: string | null) => void;
  clearChat: () => void;
  clearActivities: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  // Initial state
  messages: [],
  activities: [],
  isConnected: false,
  isAgentTyping: false,
  connectionError: null,
  currentStreamingId: null,
  sessionId: null,

  // Actions
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateMessage: (id, content, isComplete = false) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id
          ? { ...msg, content, isStreaming: !isComplete }
          : msg
      ),
    })),

  // Start a new streaming message
  startStreaming: (id, initialContent) =>
    set((state) => ({
      currentStreamingId: id,
      isAgentTyping: true,
      messages: [
        ...state.messages,
        {
          id,
          role: 'assistant' as const,
          content: initialContent,
          timestamp: new Date(),
          isStreaming: true,
        },
      ],
    })),

  // Append content to the current streaming message
  appendToLastMessage: (content) =>
    set((state) => {
      const streamingId = state.currentStreamingId;
      if (!streamingId) return state;

      return {
        messages: state.messages.map((msg) =>
          msg.id === streamingId
            ? { ...msg, content: msg.content + content }
            : msg
        ),
      };
    }),

  // Finish streaming
  finishStreaming: () =>
    set((state) => {
      const streamingId = state.currentStreamingId;
      if (!streamingId) return { isAgentTyping: false, currentStreamingId: null };

      return {
        currentStreamingId: null,
        isAgentTyping: false,
        messages: state.messages.map((msg) =>
          msg.id === streamingId
            ? { ...msg, isStreaming: false }
            : msg
        ),
      };
    }),

  addActivity: (activity) =>
    set((state) => ({
      activities: [activity, ...state.activities].slice(0, 50), // Keep last 50
    })),

  updateActivity: (id, updates) =>
    set((state) => ({
      activities: state.activities.map((act) =>
        act.id === id ? { ...act, ...updates } : act
      ),
    })),

  setConnected: (connected) =>
    set({ isConnected: connected, connectionError: null }),

  setAgentTyping: (typing) =>
    set({ isAgentTyping: typing }),

  setConnectionError: (error) =>
    set({ connectionError: error, isConnected: false }),

  setSessionId: (id) =>
    set({ sessionId: id }),

  clearChat: () =>
    set({ messages: [] }),

  clearActivities: () =>
    set({ activities: [] }),
}));
