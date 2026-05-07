import { useState } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface ThinkingBlockProps {
  thinking: string;
  isThinking: boolean;
}

export function ThinkingBlock({ thinking, isThinking }: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // While actively thinking, auto-expand
  const showExpanded = isThinking || isExpanded;

  return (
    <div className="mb-3">
      {/* Thinking header — clickable to expand/collapse */}
      <button
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex items-center gap-2 text-xs group cursor-pointer"
      >
        <div
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all",
            isThinking
              ? "border-primary/30 bg-primary/10 text-primary"
              : "border-border bg-muted/50 text-muted-foreground hover:text-foreground hover:border-muted-foreground/50"
          )}
        >
          <Brain className={cn("w-3 h-3", isThinking && "animate-pulse")} />
          <span className="font-medium">{isThinking ? "Thinking..." : "Thought process"}</span>
          {showExpanded ? (
            <ChevronDown className="w-3 h-3" />
          ) : (
            <ChevronRight className="w-3 h-3" />
          )}
        </div>
      </button>

      {/* Thinking content — expandable */}
      {showExpanded && thinking && (
        <div
          className={cn(
            "mt-2 ml-1 overflow-hidden transition-all duration-300",
            showExpanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
          )}
        >
          <div 
            className="text-[12px] leading-relaxed text-muted-foreground pl-3 border-l-2 border-primary/20 max-h-[400px] overflow-y-auto"
          >
            {thinking}
            {isThinking && (
              <span className="inline-block w-1 h-[11px] bg-primary rounded-[1px] ml-0.5 align-text-bottom animate-pulse" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
