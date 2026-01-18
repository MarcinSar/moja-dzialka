import { create } from 'zustand';
import type { ChatMessage, AgentActivity } from '@/types';

interface ChatState {
  // Chat state
  messages: ChatMessage[];
  activities: AgentActivity[];
  isConnected: boolean;
  isAgentTyping: boolean;
  connectionError: string | null;

  // Session
  sessionId: string | null;

  // Actions
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, content: string, isComplete?: boolean) => void;
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
