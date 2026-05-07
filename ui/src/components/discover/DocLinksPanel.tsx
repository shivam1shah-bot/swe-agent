import { useState } from "react";
import { ChevronDown, ChevronRight, BookOpen, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DocLink } from "@/types/discover";

interface DocLinksPanelProps {
  docLinks: DocLink[];
}

export function DocLinksPanel({ docLinks }: DocLinksPanelProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="p-0">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium hover:bg-accent/50 transition-colors"
        >
          <BookOpen className="h-4 w-4 text-blue-500" />
          <span>Documentation</span>
          <Badge variant="secondary" className="text-xs">
            {docLinks.length}
          </Badge>
          <span className="ml-auto">
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </span>
        </button>
      </CardHeader>

      {expanded && (
        <CardContent className="border-t divide-y divide-border p-0">
          {docLinks.map((link, i) => (
            <a
              key={i}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 px-4 py-3 hover:bg-accent/30 transition-colors group"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm text-foreground group-hover:text-primary transition-colors truncate">
                  {link.title}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">{link.source}</p>
              </div>
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary flex-shrink-0 transition-colors" />
            </a>
          ))}
        </CardContent>
      )}
    </Card>
  );
}
