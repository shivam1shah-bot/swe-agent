import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Save, Share2, Telescope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatMessageBubble } from "@/components/discover/ChatMessageBubble";
import { ChatInput } from "@/components/discover/ChatInput";
import { ChatSidebar, refreshSidebar } from "@/components/discover/ChatSidebar";
import { ChatMessage, StoredMessagePayload } from "@/types/discover";
import { streamDiscover } from "@/services/discover/discover.service";
import { handoffService } from "@/services/discover/handoff.service";
import {
  conversationService,
  ConversationServiceError,
} from "@/services/discover/conversation.service";
import {
  saveChatEntryFull,
  getChatEntry,
  getChatHistory,
  fromStored,
  toStored,
  updateChatEntry,
  updateChatEntryMeta,
  defaultTitleFromMessages,
} from "@/utils/discover-chat-history";
import { sessionCacheGet, sessionCacheSet } from "@/utils/discover-session-cache";
import { useCurrentUser } from "@/hooks/use-current-user";

/** Convert current messages to API-safe payload. */
function toMessagePayload(messages: ChatMessage[]): StoredMessagePayload[] {
  const stored = toStored(messages);
  return stored.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    code_refs: m.code_refs,
    doc_links: m.doc_links?.map((d) => (typeof d === "string" ? d : d.url)),
    timestamp: typeof m.timestamp === "string" ? m.timestamp : new Date(m.timestamp).toISOString(),
  }));
}

export function DiscoverSearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useCurrentUser();

  const query = searchParams.get("q") || "";
  const chatId = searchParams.get("id") || "";
  const bootstrapKey = searchParams.get("bootstrap_key") || "";

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const sessionIdRef = useRef<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastLoadedChatId = useRef<string>("");
  const handoffRefIdRef = useRef<string | null>(null);
  const bootstrapKeyPendingRemovalRef = useRef<string | null>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Keep sessionId ref in sync
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  /** Cancel any in-flight stream. */
  const cancelStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      cancelStream();

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };

      const assistantId = crypto.randomUUID();
      const streamStartedAt = Date.now();
      const streamingMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isLoading: true,
        isProcessing: true,
        startedAt: streamStartedAt,
      };

      setMessages((prev) => [...prev, userMessage, streamingMessage]);
      setIsLoading(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamDiscover(
          {
            query: text,
            skill_name: "discover",
            session_id: sessionIdRef.current,
          },
          {
            onThinkingStart: () => {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.id !== assistantId) return prev;
                return [...prev.slice(0, -1), { ...last, isLoading: false, isThinking: true, thinking: "" }];
              });
            },
            onThinking: (chunk) => {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.id !== assistantId) return prev;
                return [...prev.slice(0, -1), { ...last, thinking: (last.thinking || "") + chunk, isThinking: true }];
              });
            },
            onToolUseStart: (toolName) => {
              const labels: Record<string, string> = {
                Skill: "Invoking skill",
                Bash: "Running command",
                Read: "Reading files",
                Grep: "Searching code",
                Glob: "Finding files",
                Task: "Running sub-task",
              };
              const status = labels[toolName] || `Using ${toolName}`;
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.id !== assistantId) return prev;
                return [...prev.slice(0, -1), { ...last, processingStatus: status }];
              });
            },
            onContentBlockStop: () => {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.id !== assistantId) return prev;
                return [...prev.slice(0, -1), { ...last, isThinking: false }];
              });
            },
            onText: (chunk) => {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.id !== assistantId) return prev;
                return [
                  ...prev.slice(0, -1),
                  { ...last, content: last.content + chunk, isLoading: false, isStreaming: true, isThinking: false },
                ];
              });
            },
            onSessionId: (sid) => {
              setSessionId(sid);
              // Stream confirmed started — safe to remove bootstrap sessionStorage now.
              const pendingKey = bootstrapKeyPendingRemovalRef.current;
              if (pendingKey) {
                bootstrapKeyPendingRemovalRef.current = null;
                sessionStorage.removeItem(pendingKey);
              }
              const refId = handoffRefIdRef.current;
              if (refId) {
                handoffRefIdRef.current = null;
                handoffService.attachSession(refId, sid).catch(() => {
                  // Best-effort; session attach failure is non-critical.
                });
              }
              // Seed the session cache with current messages
              setMessages((prev) => {
                sessionCacheSet(sid, toStored(prev));
                return prev;
              });
            },
            onError: (error, errorType) => {
              if (errorType === "SessionError") {
                setSessionId(undefined);
              }
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.id !== assistantId) return prev;
                return [
                  ...prev.slice(0, -1),
                  {
                    ...last,
                    content: `Sorry, an error occurred.\n\n\`${error}\``,
                    isLoading: false,
                    isStreaming: false,
                    isProcessing: false,
                    processingStatus: undefined,
                  },
                ];
              });
              setIsLoading(false);
            },
            onDone: () => {
              const completedAt = Date.now();
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last.id !== assistantId) return prev;
                const updated = [
                  ...prev.slice(0, -1),
                  { ...last, isStreaming: false, isProcessing: false, processingStatus: undefined, completedAt },
                ];
                // Persist to session cache
                const sid = sessionIdRef.current;
                if (sid) sessionCacheSet(sid, toStored(updated));
                return updated;
              });
              setIsLoading(false);
            },
          },
          controller.signal,
        );
      } catch (error) {
        if (controller.signal.aborted) {
          // Stream was aborted — remove incomplete assistant bubble
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.id !== assistantId) return prev;
            return prev.slice(0, -1);
          });
          setIsLoading(false);
          return;
        }
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last.id !== assistantId) return prev;
          return [
            ...prev.slice(0, -1),
            {
              ...last,
              content: `Sorry, I encountered an error while searching. Please try again.\n\n\`${error instanceof Error ? error.message : "Unknown error"}\``,
              isLoading: false,
              isStreaming: false,
              isProcessing: false,
            },
          ];
        });
        setIsLoading(false);
      }
    },
    [cancelStream]
  );

  // Load conversation from URL params
  useEffect(() => {
    // Bootstrap (handoff from Slack)
    if (bootstrapKey) {
      const bootstrapMarker = `bootstrap:${bootstrapKey}`;
      if (lastLoadedChatId.current === bootstrapMarker) return;
      lastLoadedChatId.current = bootstrapMarker;

      cancelStream();
      const raw = sessionStorage.getItem(bootstrapKey);
      if (!raw) {
        setMessages([]);
        setSessionId(undefined);
        setActiveChatId(null);
        setIsLoading(false);
        return;
      }

      let initialQuery = "";
      let resumeSessionId: string | undefined;
      let runtimeSessionId: string | undefined;
      let autoRun = true;
      let refId: string | undefined;
      try {
        const parsed = JSON.parse(raw) as {
          initial_query?: string;
          resume_session_id?: string | null;
          runtime_session_id?: string;
          auto_run?: boolean;
          ref_id?: string;
        };
        initialQuery = (parsed.initial_query || "").trim();
        resumeSessionId = parsed.resume_session_id ?? undefined;
        runtimeSessionId = parsed.runtime_session_id;
        autoRun = parsed.auto_run !== false;
        refId = parsed.ref_id;
      } catch {
        initialQuery = "";
      }

      // Try to resume existing session without re-running query
      if (resumeSessionId && !autoRun) {
        const cached = sessionCacheGet(resumeSessionId);
        if (cached) {
          sessionStorage.removeItem(bootstrapKey);
          const baseMessages = fromStored(cached.messages);
          setMessages(baseMessages);
          setSessionId(resumeSessionId);
          setActiveChatId(null);

          // Check for pending messages
          if (runtimeSessionId) {
            handoffService.getPendingMessages(runtimeSessionId).then((pending) => {
              if (!pending.length) return;

              const answered = pending.filter((p) => p.answer);
              const unanswered = pending.filter((p) => !p.answer);

              if (answered.length) {
                setMessages((prev) => {
                  const extra = answered.flatMap(({ question, answer }) => [
                    { id: crypto.randomUUID(), role: "user" as const, content: question, timestamp: new Date() },
                    { id: crypto.randomUUID(), role: "assistant" as const, content: answer ?? "", timestamp: new Date() },
                  ]);
                  return [...prev, ...extra];
                });
              }

              if (unanswered.length > 0) {
                const nextQuestion = unanswered[0].question;
                setTimeout(() => sendMessage(nextQuestion), 150);
              }
            }).catch(() => {
              // Best-effort: pending message fetch is non-critical.
            });
          }
          return;
        }

        // Fall back to saved history
        const history = getChatHistory();
        const entry = history.find((e) => e.session_id === resumeSessionId);
        if (entry) {
          sessionStorage.removeItem(bootstrapKey);
          setMessages(fromStored(entry.messages || []));
          setSessionId(entry.session_id);
          setActiveChatId(entry.id);
          setSearchParams({ id: entry.id }, { replace: true });
          lastLoadedChatId.current = entry.id;
          return;
        }
      }

      if (!initialQuery) {
        sessionStorage.removeItem(bootstrapKey);
        setMessages([]);
        setSessionId(undefined);
        setActiveChatId(null);
        setIsLoading(false);
        return;
      }

      // Start ephemeral session from handoff query
      bootstrapKeyPendingRemovalRef.current = bootstrapKey;
      handoffRefIdRef.current = refId ?? null;
      setMessages([]);
      setSessionId(undefined);
      setActiveChatId(null);
      setSearchParams({}, { replace: true });
      sendMessage(initialQuery);
      return;
    }

    // Load saved conversation by id
    if (chatId) {
      if (lastLoadedChatId.current === chatId) return;
      lastLoadedChatId.current = chatId;
      cancelStream();

      const entry = getChatEntry(chatId);
      if (entry && entry.messages && entry.messages.length > 0) {
        setMessages(fromStored(entry.messages));
        setSessionId(entry.session_id);
        setActiveChatId(chatId);
        setIsLoading(false);
        return;
      }

      // Re-run query if entry exists but has no messages
      if (entry && entry.query && entry.query.trim()) {
        setMessages([]);
        setSessionId(undefined);
        setActiveChatId(chatId);
        setIsLoading(false);
        sendMessage(entry.query.trim());
        return;
      }

      setMessages([]);
      setSessionId(undefined);
      setActiveChatId(chatId);
      setIsLoading(false);
      return;
    }

    // New ephemeral search from query param
    if (query) {
      cancelStream();
      setMessages([]);
      setSessionId(undefined);
      setActiveChatId(null);
      setSearchParams({}, { replace: true });
      sendMessage(query);
    }
  }, [query, chatId, bootstrapKey, sendMessage, setSearchParams, cancelStream]);

  // Cleanup on unmount
  useEffect(() => {
    return () => cancelStream();
  }, [cancelStream]);

  const handleFollowUp = (text: string) => {
    sendMessage(text);
  };

  // Save/Share enabled when content exists
  const canSaveOrShare =
    messages.length > 0 &&
    !messages.some((m) => m.isLoading || m.isThinking) &&
    messages.some((m) => m.role === "assistant" && !!m.content.trim());

  const handleSave = async () => {
    if (!canSaveOrShare) return;
    if (!user) {
      setToast("Sign in to save conversations");
      return;
    }

    const transcript = toMessagePayload(messages);
    const title = defaultTitleFromMessages(messages) || undefined;
    const serverSessionKey = sessionId || activeChatId || crypto.randomUUID();

    let currentChatId = activeChatId;
    if (!currentChatId) {
      const firstUserQuery = messages.find((m) => m.role === "user")?.content || "Saved conversation";
      currentChatId = saveChatEntryFull(firstUserQuery, messages, sessionId, title);
      if (currentChatId) {
        setActiveChatId(currentChatId);
        setSearchParams({ id: currentChatId }, { replace: true });
      }
    } else {
      updateChatEntry(currentChatId, messages, sessionId, title);
    }

    try {
      const result = await conversationService.save(serverSessionKey, transcript);
      if (currentChatId) {
        updateChatEntryMeta(currentChatId, { saved_expires_at: result.expires_at });
      }
      refreshSidebar();
      setSidebarKey((k) => k + 1);
      setToast("Saved for 14 days");
    } catch (err) {
      if (err instanceof ConversationServiceError && err.status === 401) {
        setToast("Sign in to save conversations");
        return;
      }
      setToast(err instanceof Error ? err.message : "Save failed");
    }
  };

  const handleShare = async () => {
    if (!canSaveOrShare) return;
    if (!user) {
      setToast("Sign in to share conversations");
      return;
    }

    const transcript = toMessagePayload(messages);
    const serverSessionKey = sessionId || activeChatId || crypto.randomUUID();

    let currentChatId = activeChatId;
    if (!currentChatId) {
      const firstUserQuery = messages.find((m) => m.role === "user")?.content || "Shared conversation";
      currentChatId = saveChatEntryFull(firstUserQuery, messages, sessionId);
      if (currentChatId) {
        setActiveChatId(currentChatId);
        setSearchParams({ id: currentChatId }, { replace: true });
      }
    } else {
      updateChatEntry(currentChatId, messages, sessionId);
    }

    try {
      const result = await conversationService.share(serverSessionKey, transcript);
      await navigator.clipboard.writeText(result.url);
      if (currentChatId) {
        updateChatEntryMeta(currentChatId, {
          share_url: result.url,
          share_expires_at: result.expires_at,
        });
      }
      refreshSidebar();
      setSidebarKey((k) => k + 1);
      setToast("Link copied! Valid for 7 days");
    } catch (err) {
      if (err instanceof ConversationServiceError && err.status === 401) {
        setToast("Sign in to share conversations");
        return;
      }
      setToast(err instanceof Error ? err.message : "Share failed");
    }
  };

  // Clear toast after 3 seconds
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  return (
    <div className="h-[calc(100vh-4rem)] flex bg-background">
      {/* Left sidebar */}
      <aside className="hidden md:block flex-shrink-0">
        <ChatSidebar key={sidebarKey} activeChatId={activeChatId} />
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex-shrink-0 border-b bg-card/60 backdrop-blur-md">
          <div className="px-6 py-3 flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/discover")}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>

            <div className="flex items-center gap-2.5">
              <div className="bg-primary/10 p-1.5 rounded-lg border border-border">
                <Telescope className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h1 className="text-sm font-semibold">Discover</h1>
              </div>
            </div>

            <div className="ml-auto flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSave}
                disabled={!canSaveOrShare}
                title={
                  !user
                    ? "Sign in to save"
                    : !canSaveOrShare
                    ? "Waiting for response to start..."
                    : "Save conversation (14 days)"
                }
              >
                <Save className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleShare}
                disabled={!canSaveOrShare}
                title={
                  !user
                    ? "Sign in to share"
                    : !canSaveOrShare
                    ? "Waiting for response to start..."
                    : "Share read-only link (7 days)"
                }
              >
                <Share2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </header>

        {/* Chat messages */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">
            {messages.map((message) => (
              <ChatMessageBubble 
                key={message.id} 
                message={message} 
                sessionId={sessionId}
                userEmail={user?.email || null}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </main>

        {/* Chat input */}
        <div className="flex-shrink-0 border-t bg-card/60 backdrop-blur-md">
          <div className="max-w-5xl mx-auto px-6 py-4">
            <ChatInput
              onSend={handleFollowUp}
              disabled={isLoading}
              placeholder="Ask a follow-up question..."
            />
          </div>
        </div>

        {/* Toast */}
        {toast && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-card/80 backdrop-blur-md text-foreground text-sm shadow-lg border border-border z-50">
            {toast}
          </div>
        )}
      </div>
    </div>
  );
}
