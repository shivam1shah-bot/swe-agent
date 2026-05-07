import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquare, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getChatHistory, clearChatHistory } from "@/utils/discover-chat-history";
import type { ChatHistoryEntry } from "@/types/discover";

function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

interface ChatHistoryProps {
  onSelect?: () => void;
}

export function ChatHistory({ onSelect }: ChatHistoryProps) {
  const navigate = useNavigate();
  const [history, setHistory] = useState<ChatHistoryEntry[]>([]);

  // Refresh history when component mounts
  useEffect(() => {
    setHistory(getChatHistory());
  }, []);

  // Listen for history updates from other components
  useEffect(() => {
    const handleHistoryUpdate = () => {
      setHistory(getChatHistory());
    };
    
    window.addEventListener("discover-history-updated", handleHistoryUpdate);
    return () => window.removeEventListener("discover-history-updated", handleHistoryUpdate);
  }, []);

  const handleClear = useCallback(() => {
    clearChatHistory();
    setHistory([]);
  }, []);

  const handleClick = useCallback(
    (entry: ChatHistoryEntry) => {
      if (entry.messages && entry.messages.length > 0) {
        navigate(`/discover/search?id=${encodeURIComponent(entry.id)}`);
      } else {
        navigate(`/discover/search?q=${encodeURIComponent(entry.query)}`);
      }
      onSelect?.();
    },
    [navigate, onSelect]
  );

  if (history.length === 0) return null;

  return (
    <div className="max-w-4xl mx-auto px-4 mt-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Previous Chats
        </h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClear}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="h-3 w-3" />
          Clear
        </Button>
      </div>

      <ul className="max-h-64 overflow-y-auto space-y-1">
        {history.map((entry) => (
          <li key={entry.id}>
            <button
              type="button"
              onClick={() => handleClick(entry)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left",
                "hover:bg-accent transition-colors group border border-transparent hover:border-border"
              )}
            >
              <MessageSquare className="h-4 w-4 flex-shrink-0 text-muted-foreground group-hover:text-primary transition-colors" />
              <span className="flex-1 text-sm text-foreground truncate">
                {entry.title || entry.query}
              </span>
              <span className="flex-shrink-0 text-xs text-muted-foreground">
                {formatRelativeTime(entry.timestamp)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Export refresh function for external use
export function refreshChatHistory() {
  window.dispatchEvent(new Event("discover-history-updated"));
}
