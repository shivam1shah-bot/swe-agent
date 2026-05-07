import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState, useEffect, useCallback } from "react";
import { ThumbsUp, ThumbsDown, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ChatMessage } from "@/types/discover";
import { CodeRefsPanel } from "./CodeRefsPanel";
import { DocLinksPanel } from "./DocLinksPanel";
import { ThinkingBlock } from "./ThinkingBlock";
import { getApiBaseUrl } from "@/lib/environment";

function getUserInitials(email: string | null): string {
  if (!email) return "U";
  const local = email.split("@")[0];
  const parts = local.split(".");
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return parts[0][0].toUpperCase();
}

interface UserAvatarProps {
  email: string | null;
}

function UserAvatar({ email }: UserAvatarProps) {
  return (
    <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-semibold">
      {getUserInitials(email)}
    </div>
  );
}

interface ElapsedTimerProps {
  startedAt?: number;
  completedAt?: number;
}

function ElapsedTimer({ startedAt, completedAt }: ElapsedTimerProps) {
  const [elapsed, setElapsed] = useState<number>(0);

  useEffect(() => {
    if (!startedAt) return;
    if (completedAt) {
      setElapsed(completedAt - startedAt);
      return;
    }
    // Live ticker while still running
    const interval = setInterval(() => {
      setElapsed(Date.now() - startedAt);
    }, 100);
    return () => clearInterval(interval);
  }, [startedAt, completedAt]);

  if (!startedAt) return null;

  const seconds = (elapsed / 1000).toFixed(1);
  return (
    <span className="text-[10px] text-muted-foreground tabular-nums">
      {completedAt ? `${seconds}s` : `${seconds}s...`}
    </span>
  );
}

// ── Feedback buttons ─────────────────────────────────────────────────────────

type FeedbackRating = "thumbs_up" | "thumbs_down";

interface FeedbackButtonsProps {
  messageId: string;
  sessionId?: string;
}

function FeedbackButtons({ messageId, sessionId }: FeedbackButtonsProps) {
  const [voted, setVoted] = useState<FeedbackRating | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = useCallback(
    async (rating: FeedbackRating) => {
      if (rating === voted || submitting) return;
      setSubmitting(true);
      try {
        const apiBaseUrl = getApiBaseUrl();
        const token = localStorage.getItem("auth_token");
        await fetch(`${apiBaseUrl}/api/v1/feedback/ui`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ 
            message_id: messageId, 
            session_id: sessionId ?? null, 
            rating 
          }),
        });
        setVoted(rating);
      } catch {
        // Non-critical — silently ignore network errors.
      } finally {
        setSubmitting(false);
      }
    },
    [messageId, sessionId, voted, submitting]
  );

  return (
    <div className="flex items-center gap-1 mt-2">
      <span className="text-[10px] text-muted-foreground mr-1">Was this helpful?</span>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => submit("thumbs_up")}
        disabled={voted === "thumbs_up" || submitting}
        title={voted === "thumbs_up" ? "Marked as helpful" : "Mark as helpful"}
        className={cn(
          "h-7 w-7",
          voted === "thumbs_up"
            ? "text-green-500 cursor-default"
            : "text-muted-foreground hover:text-green-500 hover:bg-accent"
        )}
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => submit("thumbs_down")}
        disabled={voted === "thumbs_down" || submitting}
        title={voted === "thumbs_down" ? "Marked as not helpful" : "Mark as not helpful"}
        className={cn(
          "h-7 w-7",
          voted === "thumbs_down"
            ? "text-destructive cursor-default"
            : "text-muted-foreground hover:text-destructive hover:bg-accent"
        )}
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </Button>
      {voted && (
        <span className="text-[10px] text-muted-foreground ml-1">
          {voted === "thumbs_up" ? "Marked helpful" : "Thanks for the feedback"}
        </span>
      )}
    </div>
  );
}

// ── Main bubble ───────────────────────────────────────────────────────────────

interface ChatMessageBubbleProps {
  message: ChatMessage;
  sessionId?: string;
  userEmail?: string | null;
}

export function ChatMessageBubble({ 
  message, 
  sessionId, 
  userEmail = null
}: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex gap-3 flex-row-reverse">
        <div className="flex-shrink-0 mt-1">
          <UserAvatar email={userEmail} />
        </div>
        <div className="flex-1 min-w-0 flex flex-col items-end">
          <div className="rounded-2xl rounded-tr-md px-4 py-2.5 bg-primary text-primary-foreground max-w-[75%]">
            <p className="text-[13px] leading-relaxed">{message.content}</p>
          </div>
          <p className="text-[10px] text-muted-foreground mt-1 mr-1">
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
      </div>
    );
  }

  const statusLabel = message.processingStatus || "Processing";

  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 mt-1">
        <div className="w-7 h-7 rounded-full bg-accent border border-border flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-accent-foreground" />
        </div>
      </div>

      <div className="flex-1 min-w-0">
        {message.isLoading ? (
          <div className="flex items-center gap-2.5 py-2">
            <div className="flex gap-1">
              <span
                className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"
                style={{ animationDelay: "0ms" }}
              />
              <span
                className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"
                style={{ animationDelay: "150ms" }}
              />
              <span
                className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"
                style={{ animationDelay: "300ms" }}
              />
            </div>
            <span className="text-xs text-muted-foreground">Thinking...</span>
          </div>
        ) : (
          <>
            {/* Thinking block — shown above response content */}
            {(message.thinking || message.isThinking) && (
              <ThinkingBlock
                thinking={message.thinking || ""}
                isThinking={message.isThinking || false}
              />
            )}

            {/* Processing status — shows current agent activity (tool invocations) */}
            {message.isProcessing && !message.isThinking && (
              <div className="flex items-center gap-2.5 py-2">
                <div className="flex gap-1">
                  <span
                    className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
                <span className="text-xs text-muted-foreground transition-all duration-300">
                  {statusLabel}...
                </span>
              </div>
            )}

            {/* Main response content */}
            {message.content && (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                {(message.isStreaming || message.isProcessing) && (
                  <span className="inline-block w-1 h-[14px] bg-primary rounded-[1px] ml-0.5 align-text-bottom animate-pulse" />
                )}
              </div>
            )}

            {!message.isStreaming && !message.isProcessing && (
              <div className="mt-4 space-y-3">
                {message.code_refs && message.code_refs.length > 0 && (
                  <CodeRefsPanel codeRefs={message.code_refs} />
                )}
                {message.doc_links && message.doc_links.length > 0 && (
                  <DocLinksPanel docLinks={message.doc_links} />
                )}
                {/* Feedback buttons — only on completed assistant messages with content */}
                {message.content && !message.isLoading && (
                  <FeedbackButtons messageId={message.id} sessionId={sessionId} />
                )}
              </div>
            )}
          </>
        )}

        <div className="flex items-center gap-2 mt-1.5">
          <span className="text-[10px] text-muted-foreground">
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
          {message.startedAt && (
            <>
              <span className="text-[10px] text-muted-foreground">·</span>
              <ElapsedTimer startedAt={message.startedAt} completedAt={message.completedAt} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
