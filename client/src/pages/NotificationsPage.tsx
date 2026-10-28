import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../components/ui/PageHeader";
import Card from "../components/ui/Card";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import Spinner from "../components/ui/Spinner";
import EmptyState from "../components/ui/EmptyState";
import { notificationService } from "../services/notification.service";
import { getErrorMessage } from "../services/api";
import { formatDateTime } from "../utils/format";
import type { Notification } from "../types";

function getNotificationIcon(type: string): string {
  switch (type) {
    case "access_request":
    case "access_approved":
    case "access_rejected":
      return "🔑";
    case "message":
    case "chat":
      return "💬";
    case "like":
      return "♥";
    case "comment":
      return "💭";
    case "follow":
      return "👤";
    default:
      return "🔔";
  }
}

export default function NotificationsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationService.list(),
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationService.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notif-unread-count"] });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationService.markAllRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notif-unread-count"] });
    },
  });

  const notifications = data?.items ?? [];
  const hasUnread = notifications.some((n) => !n.is_read);

  return (
    <>
      <PageHeader
        title="Notifications"
        description="Stay notified about access requests, messages, community interactions, and record updates."
        actions={
          hasUnread ? (
            <Button
              variant="secondary"
              size="sm"
              isLoading={markAllReadMutation.isPending}
              onClick={() => markAllReadMutation.mutate()}
            >
              Mark all as read
            </Button>
          ) : null
        }
      />

      {isLoading ? (
        <div className="py-12">
          <Spinner label="Loading notifications" />
        </div>
      ) : error ? (
        <Alert tone="danger" title="Could not load notifications">
          {getErrorMessage(error, "Please try again later.")}
        </Alert>
      ) : notifications.length === 0 ? (
        <EmptyState
          title="You're all caught up"
          description="You don't have any notifications right now."
        />
      ) : (
        <Card className="p-0 overflow-hidden">
          <div className="divide-y divide-slate-100">
            {notifications.map((item: Notification) => (
              <div
                key={item.id}
                onClick={() => {
                  if (!item.is_read) {
                    markReadMutation.mutate(item.id);
                  }
                }}
                className={`flex items-start gap-3.5 p-4 transition-colors cursor-pointer ${
                  !item.is_read
                    ? "bg-teal-50/40 hover:bg-teal-50/70"
                    : "hover:bg-slate-50"
                }`}
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-base">
                  {getNotificationIcon(item.type)}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className={`text-sm ${!item.is_read ? "font-bold text-slate-900" : "font-medium text-slate-800"}`}>
                      {item.title}
                    </p>
                    <span className="text-[11px] text-slate-400 shrink-0">
                      {formatDateTime(item.created_at)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-600 whitespace-pre-wrap">{item.body}</p>
                </div>

                {!item.is_read && (
                  <span
                    className="mt-1 h-2.5 w-2.5 rounded-full bg-teal-600 shrink-0"
                    title="Unread"
                  />
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}
