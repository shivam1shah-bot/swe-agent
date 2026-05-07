/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Zap, AlertCircle, RefreshCw, Loader, Server, Wrench } from 'lucide-react'
import { apiClient, McpServersStatusResponse, McpServer } from '@/lib/api'

const CACHE_TTL_MS = 5 * 60 * 1000 // 5 minutes

let cachedMcpStatus: McpServersStatusResponse | null = null
let cacheTimestamp = 0

export function MCPGatewayPage() {
  const [mcpStatus, setMcpStatus] = useState<McpServersStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedServer, setSelectedServer] = useState<McpServer | null>(null)
  const [serverTools, setServerTools] = useState<Array<{ name: string; full_name: string }>>([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [toolsError, setToolsError] = useState<string | null>(null)

  const fetchMcpStatus = useCallback(async (force = false) => {
    const now = Date.now()
    if (!force && cachedMcpStatus && now - cacheTimestamp < CACHE_TTL_MS) {
      setMcpStatus(cachedMcpStatus)
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.getMcpServersStatus()
      cachedMcpStatus = data as McpServersStatusResponse
      cacheTimestamp = Date.now()
      setMcpStatus(cachedMcpStatus)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load MCP server status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMcpStatus()
  }, [fetchMcpStatus])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available': return 'bg-green-500';
      case 'unavailable': return 'bg-red-500';
      default: return 'bg-yellow-500';
    }
  }

  const getStatusTextColor = (status: string) => {
    switch (status) {
      case 'available': return 'text-green-600 dark:text-green-400';
      case 'unavailable': return 'text-red-600 dark:text-red-400';
      default: return 'text-yellow-600 dark:text-yellow-400';
    }
  }

  const getStatusBgColor = (_status: string) => {
    return 'bg-card border-border';
  }

  return (
    <div className="flex-1 p-6 relative min-h-screen">
      {/* Background ambient effects */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-900 pointer-events-none" />
      
      <div className="relative z-10 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between mb-6 mt-2">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
              <Zap className="w-6 h-6 mr-2 text-purple-500" />
              Connected MCP Servers
            </h1>
            <p className="text-muted-foreground mt-1">
              Select a server to view its available tools and capabilities
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => fetchMcpStatus(true)} disabled={loading}>
            {loading ? <Loader className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
            Refresh
          </Button>
        </div>

        {loading && !mcpStatus ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Loader className="h-10 w-10 animate-spin mb-4 text-purple-500" />
            <p>Discovering MCP servers...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-16 text-red-500 bg-red-50/50 dark:bg-red-950/20 rounded-xl border border-red-100 dark:border-red-900">
            <AlertCircle className="h-12 w-12 mb-4" />
            <p className="text-lg font-medium">{error}</p>
            <Button variant="outline" onClick={() => fetchMcpStatus(true)} className="mt-4">Try Again</Button>
          </div>
        ) : mcpStatus && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {mcpStatus.servers.map((server) => (
              <Card
                key={server.type}
                className={`cursor-pointer transition-all hover:shadow-md hover:border-purple-200 dark:hover:border-purple-800 overflow-hidden ${getStatusBgColor(server.status)}`}
                onClick={async () => {
                  setSelectedServer(server)
                  setServerTools([])
                  setToolsError(null)
                  setToolsLoading(true)
                  try {
                    const data = await apiClient.getMcpServerTools(server.type)
                    setServerTools(data.tools)
                  } catch (e: any) {
                    setToolsError(e.message || 'Failed to load tools')
                  } finally {
                    setToolsLoading(false)
                  }
                }}
              >
                <div className={`h-0.5 w-full ${server.status === 'available' ? 'bg-green-500' : server.status === 'unavailable' ? 'bg-red-500' : 'bg-yellow-500'}`} />
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-white dark:bg-slate-900 rounded-lg shadow-sm">
                        <Server className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <CardTitle className="text-base">{server.name}</CardTitle>
                        <p className="text-xs font-mono text-muted-foreground mt-0.5">{server.type}</p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-600 dark:text-slate-300 line-clamp-2 mb-3 h-10">
                    {server.description}
                  </p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <div className={`w-2 h-2 rounded-full ${getStatusColor(server.status)}`} />
                      <span className={`text-xs font-medium capitalize ${getStatusTextColor(server.status)}`}>
                        {server.status}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground font-medium">
                      View Tools &rarr;
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {mcpStatus.servers.length === 0 && (
              <div className="col-span-full text-center py-12 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-dashed">
                <Server className="h-12 w-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500">No MCP servers currently connected.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tools Modal */}
      <Dialog open={!!selectedServer} onOpenChange={(open) => !open && setSelectedServer(null)}>
        <DialogContent className="sm:max-w-[700px] border-none shadow-none">
          <DialogHeader className="p-6 border-b">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <Wrench className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <DialogTitle className="text-xl">{selectedServer?.name} Tools</DialogTitle>
                <p className="text-sm text-muted-foreground">
                  Available capabilities exposed by this MCP server
                </p>
              </div>
            </div>
          </DialogHeader>
          
          <div className="p-6">
            {toolsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader className="h-6 w-6 animate-spin text-purple-500" />
              </div>
            ) : toolsError ? (
              <div className="py-8 text-center bg-red-50 dark:bg-red-950/30 rounded-xl border border-dashed border-red-200 dark:border-red-800">
                <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
                <p className="text-red-600 dark:text-red-400 font-medium mb-1">Failed to load tools</p>
                <p className="text-xs text-red-400">{toolsError}</p>
              </div>
            ) : serverTools.length > 0 ? (
              <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-2">
                <p className="text-xs text-muted-foreground mb-3">{serverTools.length} tools available</p>
                {serverTools.map((tool, idx) => (
                  <div key={idx} className="p-3 rounded-lg border bg-slate-50 dark:bg-slate-900/50 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold font-mono text-sm text-purple-700 dark:text-purple-400">
                        {tool.name}
                      </h4>
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 bg-slate-200/50 dark:bg-slate-800 px-2 py-0.5 rounded">
                        Tool
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-dashed">
                <Wrench className="h-10 w-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 font-medium mb-1">No tools configured for this server.</p>
                <p className="text-xs text-slate-400">This server is connected but has no tools in the allowed list.</p>
              </div>
            )}
          </div>
          <div className="px-6 py-4 border-t flex justify-end">
            <Button onClick={() => setSelectedServer(null)}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
