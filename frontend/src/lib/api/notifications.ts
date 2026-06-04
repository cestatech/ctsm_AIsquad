import { apiClient } from "./client";
import type { Notification, NotificationListResponse } from "@/types";

export const notificationsApi = {
  list: (params: { unread_only?: boolean; page?: number; page_size?: number }, token: string) =>
    apiClient.get<NotificationListResponse>("/notifications", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  markRead: (id: string, token: string) =>
    apiClient.post<Notification>(`/notifications/${id}/read`, { token }),

  markAllRead: (token: string) =>
    apiClient.post<void>("/notifications/read-all", { token }),
};
