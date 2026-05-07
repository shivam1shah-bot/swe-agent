import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  RefreshCw,
  Activity,
  Clock,
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader,
  Copy,
  Check
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { apiClient, Task, TaskExecutionLogs } from '@/lib/api'

export function ExecutionLogsPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const [task, setTask] = useState<Task | null>(null)
  const [executionLogs, setExecutionLogs] = useState<TaskExecutionLogs | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Load task details
  const loadTask = async () => {
    if (!taskId) return

    try {
      const taskData = await apiClient.getTask(taskId)
      setTask(taskData)
    } catch (err) {
      console.error('Failed to load task:', err)
      setError('Failed to load task details')
    }
  }

  // Load execution logs
  const loadExecutionLogs = async (isRefresh = false) => {
    if (!taskId) return

    try {
      if (isRefresh) {
        setRefreshing(true)
      }

      const logs = await apiClient.getTaskExecutionLogs(taskId)
      setExecutionLogs(logs)
      setError(null)
    } catch (err) {
      console.error('Failed to load execution logs:', err)
      setError('Failed to load execution logs')
    } finally {
      setLoading(false)
      if (isRefresh) {
        setRefreshing(false)
      }
    }
  }

  // Auto-refresh logic
  useEffect(() => {
    if (!autoRefresh || !taskId) return

    const interval = setInterval(() => {
      loadExecutionLogs(false)
    }, 3000) // Refresh every 3 seconds

    return () => clearInterval(interval)
  }, [autoRefresh, taskId])

  // Initial load
  useEffect(() => {
    if (taskId) {
      setLoading(true)
      Promise.all([
        loadTask(),
        loadExecutionLogs()
      ])
    }
  }, [taskId])

  const handleRefresh = () => {
    loadExecutionLogs(true)
  }



  if (!taskId) {
    return (
      <div className="p-6">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900">Invalid Task ID</h1>
          <p className="text-gray-600 mt-2">No task ID provided in the URL.</p>
          <Link to="/tasks">
            <Button className="mt-4">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Tasks
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      {/* Background ambient effects */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />
      
      <div className="relative z-10 max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="mb-6 mt-2">
          <div className="flex items-center gap-4 mb-4">
            <Link to="/tasks">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Tasks
              </Button>
            </Link>
            <div className="flex-1">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
                <FileText className="w-6 h-6 mr-2 text-blue-500" />
                Execution Logs
              </h1>
              <p className="text-muted-foreground mt-1">
                Task ID: {taskId}
              </p>
            </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant={autoRefresh ? "default" : "outline"}
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              <Activity className="h-4 w-4 mr-2" />
              Auto Refresh {autoRefresh ? 'On' : 'Off'}
            </Button>
          </div>
        </div>

        {/* Task Info Card */}
        {task && (
          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">{task.name}</CardTitle>
                  <CardDescription>{task.description || 'No description'}</CardDescription>
                </div>
                <div className="flex items-center gap-4">
                  <Badge variant={task.status === 'completed' ? 'default' : 'secondary'}>
                    {task.status}
                  </Badge>
                  {task.progress !== undefined && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-600">Progress:</span>
                      <span className="text-sm font-medium">{task.progress}%</span>
                    </div>
                  )}
                </div>
              </div>
            </CardHeader>
          </Card>
        )}
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 text-red-600">
              <AlertCircle className="h-5 w-5" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {loading && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 text-gray-600">
              <Loader className="h-5 w-5 animate-spin" />
              <span>Loading execution logs...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Agent Logs Section */}
      {executionLogs && (
        <AgentLogsSection
          executionLogs={executionLogs}
        />
      )}
    </div>
    </div>
  )
}

// Agent Logs Section Component
interface AgentLogsSectionProps {
  executionLogs: TaskExecutionLogs
}

function AgentLogsSection({ executionLogs }: AgentLogsSectionProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <Activity className="h-4 w-4 text-blue-500" />
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-500" />
    }
  }

  const formatLogContent = (content: string): string => {
    try {
      // Try to parse as JSON and format it nicely
      const parsed = JSON.parse(content)
      return JSON.stringify(parsed, null, 2)
    } catch {
      // If not valid JSON, return as-is
      return content
    }
  }

  const copyToClipboard = async (content: string, index: number) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Agent Logs
            </CardTitle>
            <CardDescription>
              Real-time execution logs from Claude agent
            </CardDescription>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              {executionLogs.file_status === 'active' ? (
                <Activity className="h-4 w-4 text-green-500" />
              ) : (
                <AlertCircle className="h-4 w-4 text-yellow-500" />
              )}
              <span>
                {executionLogs.file_status === 'active' ? 'Live' : 'Inactive'}
              </span>
            </div>
            <div>
              Total logs: {executionLogs.total_logs}
            </div>
            {executionLogs.last_updated && (
              <div>
                Updated: {formatTimestamp(executionLogs.last_updated)}
              </div>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {executionLogs.last_logs.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <div className="text-lg font-medium mb-2 text-foreground">No logs available</div>
            <div className="text-sm">
              {executionLogs.file_status === 'not_found'
                ? 'Agent hasn\'t started logging yet'
                : 'Logs will appear here when the agent starts working'
              }
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
            {[...executionLogs.last_logs].reverse().map((log, index) => {
              const formattedContent = formatLogContent(log.content)
              return (
                <div
                  key={`${log.log_index}-${index}`}
                  className="border border-border/50 rounded-lg p-4 bg-muted/30"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(log.status)}
                      <span className="text-sm font-medium text-foreground">
                        Log #{log.log_index}
                      </span>
                      <Badge
                        variant={log.status === 'active' ? 'default' : 'secondary'}
                        className="text-xs"
                      >
                        {log.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      {log.timestamp && (
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(log.timestamp)}
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(formattedContent, index)}
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                      >
                        {copiedIndex === index ? (
                          <Check className="h-3 w-3 text-green-500" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                  </div>
                  <div className="relative">
                    <div className="text-sm text-foreground bg-background p-3 rounded border border-border/50 max-h-96 overflow-auto">
                      <pre className="text-xs leading-relaxed font-mono whitespace-pre-wrap break-words">
                        {formattedContent}
                      </pre>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function formatTimestamp(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleString()
  } catch {
    return timestamp
  }
}