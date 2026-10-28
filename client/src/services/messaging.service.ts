import { api } from "./api";
import type { ConversationListResponse, MessageListResponse, Conversation, Message } from "../types";

export const messagingService = {
  listConversations: async (): Promise<ConversationListResponse> => {
    const res = await api.get("/conversations");
    return res.data;
  },
  startConversation: async (otherUserId: string): Promise<Conversation> => {
    const res = await api.post("/conversations", { other_user_id: otherUserId });
    return res.data;
  },
  listMessages: async (conversationId: string, skip = 0, limit = 50): Promise<MessageListResponse> => {
    const res = await api.get(`/conversations/${conversationId}/messages`, { params: { skip, limit } });
    return res.data;
  },
  sendMessage: async (conversationId: string, content: string): Promise<Message> => {
    const res = await api.post(`/conversations/${conversationId}/messages`, { content });
    return res.data;
  },
  markRead: async (conversationId: string): Promise<void> => {
    await api.patch(`/conversations/${conversationId}/read`);
  },
};
