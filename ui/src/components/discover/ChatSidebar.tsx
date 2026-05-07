import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquare, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getChatHistory, deleteChatEntry } from "@/utils/discover-chat-history";
import type { ChatHistoryEntry } from "@/types/discover";

function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d`;

  const months = Math.floor(days / 30);
  return `${months}mo`;
}

interface ChatSidebarProps {
  activeChatId?: string | null;
}

export function ChatSidebar({ activeChatId }: ChatSidebarProps) {
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

  const handleDelete = useCallback((e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteChatEntry(id);
    setHistory(getChatHistory());
  }, []);

  const handleClick = useCallback(
    (entry: ChatHistoryEntry) => {
      if (entry.messages && entry.messages.length > 0) {
        navigate(`/discover/search?id=${encodeURIComponent(entry.id)}`);
      } else {
        navigate(`/discover/search?q=${encodeURIComponent(entry.query)}`);
      }
    },
    [navigate]
  );

  const handleNewChat = () => {
    navigate("/discover");
  };

  return (
    <div className="w-64 border-r bg-card/40 backdrop-blur-sm flex flex-col h-full">
      <div className="p-4 border-b">
        <Button 
          onClick={handleNewChat}
          variant="outline" 
          className="w-full justify-start gap-2"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="p-3 space-y-1">
          {history.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              No saved conversations yet.
              <br />
              Start a chat and save it to see it here.
            </p>
          ) : (
            history.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => handleClick(entry)}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors group",
                  activeChatId === entry.id
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-accent text-foreground"
                )}
              >
                <MessageSquare className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="flex-1 truncate text-xs">
                  {entry.title || entry.query}
                </span>
                <span className={cn(
                  "flex-shrink-0 text-[10px]",
                  activeChatId === entry.id ? "text-primary-foreground/70" : "text-muted-foreground"
                )}>
                  {formatRelativeTime(entry.timestamp)}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={(e) => handleDelete(e, entry.id)}
                  className={cn(
                    "h-5 w-5 flex-shrink-0 opacity-0 group-hover:opacity-100",
                    activeChatId === entry.id 
                      ? "hover:bg-primary-foreground/20 text-primary-foreground" 
                      : "hover:bg-accent text-muted-foreground"
                  )}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// Export refresh function for external use
export function refreshSidebar() {
  window.dispatchEvent(new Event("discover-history-updated"));
}
