import { useState } from "react";
import { ChevronDown, ChevronRight, FileCode, Copy, Check } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CodeRef } from "@/types/discover";

interface CodeRefsPanelProps {
  codeRefs: CodeRef[];
}

export function CodeRefsPanel({ codeRefs }: CodeRefsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopy = (snippet: string, index: number) => {
    navigator.clipboard.writeText(snippet);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="p-0">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium hover:bg-accent/50 transition-colors"
        >
          <FileCode className="h-4 w-4 text-primary" />
          <span>Code References</span>
          <Badge variant="secondary" className="text-xs">
            {codeRefs.length}
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
          {codeRefs.map((ref, i) => (
            <div key={i} className="px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs font-medium text-primary truncate">
                    {ref.repository}
                  </span>
                  <span className="text-muted-foreground">/</span>
                  <span className="text-xs text-foreground truncate">{ref.file_path}</span>
                  <span className="text-xs text-muted-foreground flex-shrink-0">L{ref.line_number}</span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleCopy(ref.snippet, i)}
                  className="flex-shrink-0 h-7 w-7"
                  title="Copy snippet"
                >
                  {copiedIndex === i ? (
                    <Check className="h-3.5 w-3.5 text-green-500" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </Button>
              </div>
              <pre className="text-xs bg-muted border rounded-lg p-3 overflow-x-auto text-foreground leading-relaxed">
                <code>{ref.snippet}</code>
              </pre>
            </div>
          ))}
        </CardContent>
      )}
    </Card>
  );
}
