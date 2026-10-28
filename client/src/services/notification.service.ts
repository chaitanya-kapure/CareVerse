import { api } from "./api";
import type { NotificationListResponse } from "../types";

export const notificationService = {
  list: async (skip = 0, limit = 30): Promise<NotificationListResponse> => {
    const res = await api.get("/notifications", { params: { skip, limit } });
    return res.data;
  },
  unreadCount: async (): Promise<{ count: number }> => {
    const res = await api.get("/notifications/unread-count");
    return res.data;
  },
  markRead: async (id: string): Promise<void> => {
    await api.patch(`/notifications/${id}/read`);
  },
  markAllRead: async (): Promise<void> => {
    await api.patch("/notifications/read-all");
  },
};
