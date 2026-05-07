import { useNavigate } from "react-router-dom";
import { Telescope, Settings, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SearchBar } from "@/components/discover/SearchBar";
import { ChatHistory } from "@/components/discover/ChatHistory";

export function DiscoverPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-card/60 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-primary/10 p-2 rounded-xl border border-border">
                <Telescope className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">
                  Discover
                </h1>
                <p className="text-xs text-muted-foreground">
                  AI-powered search across your engineering knowledge
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative group">
                <Button variant="ghost" size="sm" disabled>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Evals
                </Button>
                <div className="absolute right-0 top-full mt-2 px-3 py-1.5 bg-card/80 backdrop-blur-md text-xs text-muted-foreground rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20 border border-border">
                  Coming Soon
                </div>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/settings")}
              >
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 py-16">
        {/* Hero Section */}
        <div className="max-w-4xl mx-auto px-4 mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight mb-4">
            Search across all your engineering knowledge
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Ask questions in natural language and get answers from GitHub, 
            Google Drive, Slack, AWS, and 10+ connected data sources.
          </p>
        </div>

        {/* Search Bar */}
        <SearchBar />

        {/* Chat History */}
        <ChatHistory />
      </main>

      {/* Footer */}
      <footer className="border-t mt-auto">
        <div className="max-w-7xl mx-auto px-4 py-6 text-center">
          <p className="text-sm text-muted-foreground">
            Made with <span className="text-red-400">♥</span> from Engineering
          </p>
        </div>
      </footer>
    </div>
  );
}
