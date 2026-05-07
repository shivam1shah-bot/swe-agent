import { useState, useEffect } from "react";
import { Command, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        document.getElementById("discover-search")?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/discover/search?q=${encodeURIComponent(query)}`);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 mb-12">
      <form onSubmit={handleSearch}>
        <div
          className={cn(
            "relative flex items-center rounded-xl border bg-card/60 backdrop-blur-md shadow-sm transition-all duration-300",
            isFocused
              ? "border-primary ring-1 ring-ring"
              : "border-border"
          )}
        >
          <Search className="absolute left-4 h-5 w-5 text-muted-foreground" />
          
          <Input
            id="discover-search"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Search across GitHub, Google Drive, Slack, AWS and 10+ Data Sources..."
            className="border-0 bg-transparent pl-12 pr-24 py-5 text-lg focus-visible:ring-0"
          />

          <div className="absolute right-4 flex items-center gap-2">
            {query ? (
              <kbd className="hidden md:flex items-center gap-1 px-2 py-1 text-xs font-medium text-muted-foreground bg-muted rounded border">
                <span>Enter</span>
              </kbd>
            ) : (
              <kbd className="hidden md:flex items-center gap-1 px-2 py-1 text-xs font-medium text-muted-foreground bg-muted rounded border">
                <Command className="h-3 w-3" />
                <span>K</span>
              </kbd>
            )}
          </div>
        </div>
      </form>

      <div className="flex justify-center mt-6">
        <div className="relative group">
          <Button
            variant="outline"
            disabled
            className="gap-2"
          >
            <span>⚙️</span>
            <span>Select Agents</span>
            <Badge variant="secondary">Coming Soon</Badge>
          </Button>
          <div className="absolute left-0 bottom-full mb-2 w-72 p-3 bg-card/80 backdrop-blur-md text-foreground text-xs rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 border border-border">
            <p className="font-medium mb-1">Select Agents</p>
            <p className="text-muted-foreground leading-relaxed">
              Narrow the search space by choosing specific agents to find more relevant answers
              faster — useful when you already know where the information lives.
            </p>
            <div className="absolute left-6 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-card/80" />
          </div>
        </div>
      </div>
    </div>
  );
}
