import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../components/ui/PageHeader";
import Card from "../components/ui/Card";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import Spinner from "../components/ui/Spinner";
import EmptyState from "../components/ui/EmptyState";
import { useAuth } from "../hooks/useAuth";
import { messagingService } from "../services/messaging.service";
import { getErrorMessage } from "../services/api";
import { formatDateTime } from "../utils/format";
import type { Conversation } from "../types";

export default function MessagingPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messageText, setMessageText] = useState("");
  const [showNewChatModal, setShowNewChatModal] = useState(false);
  const [newChatUserId, setNewChatUserId] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Conversations query
  const {
    data: convData,
    isLoading: isConvLoading,
    error: convError,
  } = useQuery({
    queryKey: ["conversations"],
    queryFn: messagingService.listConversations,
    refetchInterval: 10_000,
  });

  const conversations = convData?.items ?? [];

  // Messages query for selected conversation
  const {
    data: msgData,
    isLoading: isMsgLoading,
    error: msgError,
  } = useQuery({
    queryKey: ["messages", selectedConversation?.id],
    queryFn: () =>
      selectedConversation
        ? messagingService.listMessages(selectedConversation.id)
        : Promise.resolve({ items: [], total: 0 }),
    enabled: !!selectedConversation?.id,
    refetchInterval: 5_000,
  });

  const messages = msgData?.items ?? [];

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  // When selected conversation changes, mark as read
  useEffect(() => {
    if (selectedConversation) {
      messagingService.markRead(selectedConversation.id).then(() => {
        queryClient.invalidateQueries({ queryKey: ["conversations"] });
      }).catch(() => {
        // silently ignore read receipt failure
      });
    }
  }, [selectedConversation, queryClient]);

  const sendMutation = useMutation({
    mutationFn: (text: string) => {
      if (!selectedConversation) throw new Error("No conversation selected");
      return messagingService.sendMessage(selectedConversation.id, text);
    },
    onSuccess: () => {
      setMessageText("");
      queryClient.invalidateQueries({ queryKey: ["messages", selectedConversation?.id] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const startChatMutation = useMutation({
    mutationFn: (targetId: string) => messagingService.startConversation(targetId),
    onSuccess: (newConv) => {
      setShowNewChatModal(false);
      setNewChatUserId("");
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setSelectedConversation(newConv);
    },
  });

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageText.trim() || !selectedConversation) return;
    sendMutation.mutate(messageText.trim());
  };

  const handleStartChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newChatUserId.trim()) return;
    startChatMutation.mutate(newChatUserId.trim());
  };

  return (
    <>
      <PageHeader
        title="Direct Messages"
        description="Private, encrypted clinical communication with authorized clinicians and patients."
        actions={
          <Button
            size="sm"
            onClick={() => setShowNewChatModal(true)}
          >
            New Conversation
          </Button>
        }
      />

      {showNewChatModal && (
        <Card title="Start New Conversation" className="mb-4 bg-teal-50/40 border-teal-200">
          <form onSubmit={handleStartChat} className="space-y-3">
            <div>
              <label htmlFor="user-id-input" className="block text-xs font-medium text-slate-700 mb-1">
                Recipient User ID
              </label>
              <input
                id="user-id-input"
                type="text"
                value={newChatUserId}
                onChange={(e) => setNewChatUserId(e.target.value)}
                placeholder="Paste the user ID of your doctor or patient"
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
                required
              />
              <p className="mt-1 text-xs text-slate-500">
                You can start conversations with authorized contacts or discover clinicians in the directory.
              </p>
            </div>

            {startChatMutation.error && (
              <Alert tone="danger">
                {getErrorMessage(startChatMutation.error, "Could not start conversation.")}
              </Alert>
            )}

            <div className="flex items-center gap-2">
              <Button
                type="submit"
                size="sm"
                isLoading={startChatMutation.isPending}
                disabled={!newChatUserId.trim()}
              >
                Start Chat
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setShowNewChatModal(false);
                  setNewChatUserId("");
                  startChatMutation.reset();
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-[650px] border border-slate-200 rounded-lg bg-white overflow-hidden shadow-sm">
        {/* Left Panel: Conversation List */}
        <div className="border-r border-slate-200 flex flex-col h-full bg-slate-50/50">
          <div className="p-3 border-b border-slate-200 bg-white">
            <h3 className="text-sm font-semibold text-slate-900">Conversations</h3>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {isConvLoading ? (
              <div className="py-8">
                <Spinner label="Loading chats" />
              </div>
            ) : convError ? (
              <div className="p-3">
                <Alert tone="danger">
                  {getErrorMessage(convError, "Failed to load chats.")}
                </Alert>
              </div>
            ) : conversations.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500">
                No active conversations yet.
              </div>
            ) : (
              conversations.map((conv) => {
                const isSelected = selectedConversation?.id === conv.id;
                return (
                  <button
                    key={conv.id}
                    type="button"
                    onClick={() => setSelectedConversation(conv)}
                    className={`w-full text-left p-3 transition-colors ${
                      isSelected
                        ? "bg-teal-50 border-l-4 border-teal-700"
                        : "hover:bg-slate-100/80"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <span className="font-semibold text-sm text-slate-900 truncate">
                        {conv.other_participant_name || "Conversation"}
                      </span>
                      {conv.unread_count > 0 && (
                        <span className="flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-teal-600 px-1 text-[10px] font-bold text-white">
                          {conv.unread_count}
                        </span>
                      )}
                    </div>
                    {conv.last_message_preview && (
                      <p className="mt-1 text-xs text-slate-600 line-clamp-1">
                        {conv.last_message_preview}
                      </p>
                    )}
                    {conv.last_message_at && (
                      <p className="mt-1 text-[10px] text-slate-400">
                        {formatDateTime(conv.last_message_at)}
                      </p>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Panel: Active Conversation */}
        <div className="md:col-span-2 flex flex-col h-full bg-white">
          {selectedConversation ? (
            <>
              {/* Header */}
              <div className="p-3 border-b border-slate-200 flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-slate-900 text-sm">
                    {selectedConversation.other_participant_name || "Chat"}
                  </h3>
                  <p className="text-[11px] text-slate-500">Live conversation</p>
                </div>
              </div>

              {/* Messages Body */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/30">
                {isMsgLoading ? (
                  <div className="py-8">
                    <Spinner label="Loading messages" />
                  </div>
                ) : msgError ? (
                  <Alert tone="danger">
                    {getErrorMessage(msgError, "Could not load messages.")}
                  </Alert>
                ) : messages.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-xs text-slate-400">
                    No messages in this conversation yet. Send the first message!
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isOwn = msg.sender_id === user?.id;
                    return (
                      <div
                        key={msg.id}
                        className={`flex flex-col ${isOwn ? "items-end" : "items-start"}`}
                      >
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className="text-[11px] text-slate-400">
                            {formatDateTime(msg.created_at)}
                          </span>
                        </div>
                        <div
                          className={`max-w-[80%] rounded-lg px-3.5 py-2 text-sm shadow-xs whitespace-pre-wrap ${
                            isOwn
                              ? "bg-teal-700 text-white rounded-br-none"
                              : "bg-white text-slate-800 border border-slate-200 rounded-bl-none"
                          }`}
                        >
                          {msg.content}
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Message Input Footer */}
              <form
                onSubmit={handleSendMessage}
                className="p-3 border-t border-slate-200 flex gap-2 bg-white"
              >
                <input
                  type="text"
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  placeholder="Type a message..."
                  className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
                />
                <Button
                  type="submit"
                  disabled={!messageText.trim()}
                  isLoading={sendMutation.isPending}
                >
                  Send
                </Button>
              </form>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-6 text-center">
              <EmptyState
                title="No conversation selected"
                description="Select an existing conversation from the list or start a new one."
              />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
