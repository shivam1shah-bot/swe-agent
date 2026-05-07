/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { useState, useEffect, useCallback } from 'react'

import {
  Activity,
  RefreshCw,
  BarChart3,
  Clock,
  CheckCircle,
  XCircle,
  Pause,
  Play,
  FileText,
  Loader,
  ChevronLeft,
  ChevronRight,
  X,
  AlertCircle,
  User,
  Slack,
  Globe,
  Ticket
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
  DialogBody,
  DialogFooter,
} from '@/components/ui/dialog'
import { TaskResultDisplay } from '@/components/ui/task-result-display'
import { apiClient, Task, TaskStats, getTaskConnector } from '@/lib/api'

// Task status configurations
const statusConfig = {
  created: {
    icon: Clock,
    color: 'bg-gray-400',
    badgeVariant: 'outline' as const,
    label: 'Created'
  },
  pending: {
    icon: Clock,
    color: 'bg-yellow-500',
    badgeVariant: 'secondary' as const,
    label: 'Pending'
  },
  running: {
    icon: Play,
    color: 'bg-blue-500',
    badgeVariant: 'default' as const,
    label: 'Running'
  },
  completed: {
    icon: CheckCircle,
    color: 'bg-green-500',
    badgeVariant: 'default' as const,
    label: 'Completed'
  },
  failed: {
    icon: XCircle,
    color: 'bg-red-500',
    badgeVariant: 'destructive' as const,
    label: 'Failed'
  },
  cancelled: {
    icon: Pause,
    color: 'bg-gray-500',
    badgeVariant: 'outline' as const,
    label: 'Cancelled'
  },
  waiting_for_event: {
    icon: Clock,
    color: 'bg-purple-500',
    badgeVariant: 'secondary' as const,
    label: 'Waiting'
  }
}

interface PaginationProps {
  currentPage: number
  onPageChange: (page: number) => void
  currentDataSize: number
  itemsPerPage: number
}

function Pagination({ currentPage, onPageChange, currentDataSize, itemsPerPage }: PaginationProps) {
  const hasNextPage = currentDataSize === itemsPerPage
  const hasPrevPage = currentPage > 1

  return (
    <div className="flex items-center justify-center space-x-2">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={!hasPrevPage}
      >
        <ChevronLeft className="w-4 h-4" />
        Previous
      </Button>
      <div className="px-4 py-2 text-sm text-muted-foreground">
        Page {currentPage}
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={!hasNextPage}
      >
        Next
        <ChevronRight className="w-4 h-4" />
      </Button>
    </div>
  )
}

interface TaskStatsCardProps {
  stats: TaskStats | null
  loading: boolean
}

function TaskStatsCard({ stats, loading }: TaskStatsCardProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="animate-pulse space-y-3">
                <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-1/2" />
                <div className="h-8 bg-gray-200 dark:bg-gray-800 rounded w-1/3" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (!stats) return null

  // Ensure safe defaults
  const total = stats.total_tasks || 0
  const running = stats.by_status?.running || 0
  const completed = stats.by_status?.completed || 0
  const failed = stats.by_status?.failed || 0
  
  // Calculate completion rate safely
  const completionRate = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Tasks */}
      <Card className="hover:shadow-md transition-shadow relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Total Tasks</h3>
            <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <Activity className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            </div>
          </div>
          <div className="text-3xl font-bold">{total}</div>
        </CardContent>
      </Card>

      {/* Running Tasks */}
      <Card className="hover:shadow-md transition-shadow relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-yellow-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Running</h3>
            <div className="h-8 w-8 rounded-full bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center">
              <Play className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
            </div>
          </div>
          <div className="text-3xl font-bold">{running}</div>
        </CardContent>
      </Card>

      {/* Completed Tasks */}
      <Card className="hover:shadow-md transition-shadow relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-green-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Completed</h3>
            <div className="h-8 w-8 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
              <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
            </div>
          </div>
          <div className="flex items-baseline space-x-2">
            <div className="text-3xl font-bold">{completed}</div>
            <div className="text-sm font-medium text-green-600 dark:text-green-400">
              ({completionRate}%)
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Failed Tasks */}
      <Card className="hover:shadow-md transition-shadow relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-red-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Failed</h3>
            <div className="h-8 w-8 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
              <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
            </div>
          </div>
          <div className="text-3xl font-bold">{failed}</div>
        </CardContent>
      </Card>
    </div>
  )
}

interface TaskResultModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  taskId: string | null
}

function TaskResultModal({ open, onOpenChange, taskId }: TaskResultModalProps) {
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open && taskId) {
      setLoading(true)
      // Fetch complete task data
      apiClient.getTask(taskId)
        .then(taskData => {
          setTask(taskData)
          setLoading(false)
        })
        .catch(error => {
          console.error('Failed to fetch task result:', error)
          setTask(null)
          setLoading(false)
        })
    }
  }, [open, taskId])

  return (
    <Dialog open={open} onOpenChange={onOpenChange} containerClassName="max-w-screen-2xl w-[95vw] mx-auto">
      <DialogContent className="w-full max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader className="flex-shrink-0 px-6 pt-6 pb-4">
          <DialogTitle className="flex items-center justify-between gap-4 text-xl font-semibold">
            <span className="truncate">Task Result: {task?.name || taskId}</span>
            <Badge
              variant={task?.status === 'completed' ? 'default' : 'secondary'}
              className="flex-shrink-0 px-3 py-1"
            >
              {task?.status || 'Unknown'}
            </Badge>
          </DialogTitle>
          <DialogClose onClick={() => onOpenChange(false)} />
        </DialogHeader>
        <DialogBody className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-6 pb-6">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader className="w-8 h-8 animate-spin" />
              <span className="ml-2 text-sm text-muted-foreground">Loading task details...</span>
            </div>
          ) : task ? (
            <TaskResultDisplay
              result={task.result}
              showRawData={true}
              createdAt={task.created_at}
              updatedAt={task.updated_at}
              taskStatus={task.status}
            />
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              <AlertCircle className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <h3 className="text-lg font-medium mb-2">Failed to Load Task</h3>
              <p>Unable to fetch task details. Please try again.</p>
            </div>
          )}
        </DialogBody>
        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}



const connectorConfig = {
  slack:     { label: 'Slack',     icon: Slack,  color: 'text-green-600' },
  dashboard: { label: 'Dashboard', icon: Globe,  color: 'text-blue-600' },
  devrev:    { label: 'DevRev',    icon: Ticket, color: 'text-purple-600' },
}

export function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [statsLoading, setStatsLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [currentUser, setCurrentUser] = useState<{ username: string; email?: string } | null>(null)
  const [taskUsers, setTaskUsers] = useState<{ email: string; task_count: number }[]>([])

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [ownershipFilter, setOwnershipFilter] = useState<'all' | 'my'>('all')
  const [connectorFilter, setConnectorFilter] = useState<string>('all')
  const [userEmailFilter, setUserEmailFilter] = useState<string>('')

  const [resultModalOpen, setResultModalOpen] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)

  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 15

  // Fetch current user and available task users on mount
  useEffect(() => {
    apiClient.getCurrentUser()
      .then(user => setCurrentUser(user))
      .catch(() => {})
    apiClient.getTaskUsers()
      .then(users => setTaskUsers(users))
      .catch(() => {})
  }, [])

  const loadTasks = useCallback(async (page: number = 1, showRefreshSpinner = false) => {
    try {
      if (showRefreshSpinner) setRefreshing(true)
      else setLoading(true)

      const params: Record<string, any> = { page, page_size: itemsPerPage }
      if (statusFilter !== 'all') params.status = statusFilter
      if (connectorFilter !== 'all') params.connector = connectorFilter

      // "My Tasks" — filter by current user's email
      const activeEmail = ownershipFilter === 'my'
        ? (currentUser?.email || currentUser?.username || '')
        : userEmailFilter.trim()
      if (activeEmail) params.user_email = activeEmail

      const tasksData = await apiClient.getTasks(params)
      setTasks(tasksData)
    } catch (_error) {
      console.error('Failed to load tasks:', _error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [itemsPerPage, statusFilter, connectorFilter, ownershipFilter, userEmailFilter, currentUser])

  const loadStats = useCallback(async () => {
    try {
      setStatsLoading(true)
      const statsData = await apiClient.getTaskStatistics()
      setStats(statsData)
    } catch (_error) {
      console.error('Failed to load stats:', _error)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTasks(currentPage)
    loadStats()
  }, [loadTasks, loadStats, currentPage])

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      loadTasks(currentPage, true)
      loadStats()
    }, 10000)
    return () => clearInterval(interval)
  }, [loadTasks, loadStats, currentPage])

  const handleRefresh = () => {
    loadTasks(currentPage, true)
    loadStats()
  }

  const handleViewLogs = (taskId: string) => {
    window.open(`/tasks/${taskId}/execution-logs`, '_blank')
  }

  const handleViewResult = (taskId: string) => {
    setSelectedTaskId(taskId)
    setResultModalOpen(true)
  }

  const handleCancelTask = async (taskId: string) => {
    if (!window.confirm('Are you sure you want to cancel this task?')) return
    try {
      await apiClient.killTask(taskId)
      loadTasks(currentPage, true)
    } catch (_error) {
      alert('Error cancelling task. Please try again.')
    }
  }

  // Client-side search filter only (ownership/connector filtering is server-side)
  const filteredTasks = tasks.filter(task => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    const connector = getTaskConnector(task)
    return (
      task.name.toLowerCase().includes(q) ||
      (task.description?.toLowerCase().includes(q)) ||
      (connector.user_email?.toLowerCase().includes(q)) ||
      (connector.source_id?.toLowerCase().includes(q))
    )
  })

  const formatDate = (dateString: string) => new Date(dateString).toLocaleString()

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />
      
      <div className="relative z-10 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 mt-2">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
              <Activity className="w-6 h-6 mr-2 text-blue-500" />
              Tasks
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage and monitor your workflow tasks
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Statistics Section */}
        <TaskStatsCard stats={stats} loading={statsLoading} />

        {/* Unified Tasks List */}
        <Card className="shadow-sm border-border/50">
          <CardHeader className="pb-4 border-b border-border/50">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                {/* Ownership toggle */}
                <div className="flex items-center gap-3">
                  <div className="flex bg-muted/50 p-1 rounded-lg border border-border/50 shrink-0">
                    <button
                      onClick={() => { setOwnershipFilter('all'); setCurrentPage(1) }}
                      className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${ownershipFilter === 'all' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                    >
                      All Tasks
                    </button>
                    <button
                      onClick={() => { setOwnershipFilter('my'); setUserEmailFilter(''); setCurrentPage(1) }}
                      className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-1.5 ${ownershipFilter === 'my' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                    >
                      <User className="w-3.5 h-3.5" />
                      My Tasks
                    </button>
                  </div>
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-sm font-medium">{filteredTasks.length}</Badge>
                </div>

                {/* Status + Search */}
                <div className="flex items-center gap-3 w-full sm:w-auto overflow-x-auto">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Status:</span>
                    <Select
                      value={statusFilter}
                      onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1) }}
                    >
                      <option value="all">All</option>
                      <option value="running">Running</option>
                      <option value="pending">Pending</option>
                      <option value="completed">Completed</option>
                      <option value="failed">Failed</option>
                      <option value="cancelled">Cancelled</option>
                      <option value="waiting_for_event">Waiting</option>
                    </Select>
                  </div>
                  <Input
                    placeholder="Search tasks..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full sm:w-[220px] shrink-0"
                  />
                </div>
              </div>

              {/* User filters row */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Source:</span>
                  <Select
                    value={connectorFilter}
                    onChange={(e) => { setConnectorFilter(e.target.value); setCurrentPage(1) }}
                  >
                    <option value="all">All</option>
                    <option value="slack">Slack</option>
                    <option value="dashboard">Dashboard</option>
                    <option value="devrev">DevRev</option>
                  </Select>
                </div>

                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">
                    User:
                    {taskUsers.length > 0 && (
                      <span className="ml-1 text-xs font-normal text-muted-foreground/70">({taskUsers.length})</span>
                    )}
                  </span>
                  <Select
                    value={ownershipFilter === 'my' ? (currentUser?.email || currentUser?.username || '') : userEmailFilter}
                    disabled={ownershipFilter === 'my'}
                    onChange={(e) => { setUserEmailFilter(e.target.value); setOwnershipFilter('all'); setCurrentPage(1) }}
                  >
                    <option value="">All users</option>
                    {taskUsers.map(u => (
                      <option key={u.email} value={u.email}>
                        {u.email} ({u.task_count})
                      </option>
                    ))}
                  </Select>
                </div>

                {(connectorFilter !== 'all' || userEmailFilter || ownershipFilter === 'my') && (
                  <button
                    onClick={() => { setConnectorFilter('all'); setUserEmailFilter(''); setOwnershipFilter('all'); setCurrentPage(1) }}
                    className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 underline underline-offset-2"
                  >
                    <X className="w-3 h-3" /> Clear filters
                  </button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground">
                <Loader className="w-8 h-8 animate-spin mx-auto mb-4 text-primary/50" />
                Loading tasks...
              </div>
            ) : filteredTasks.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-muted-foreground uppercase bg-muted/20 border-b border-border/50">
                    <tr>
                      <th className="px-6 py-4 font-medium min-w-[250px] w-1/2">Task</th>
                      <th className="px-6 py-4 font-medium">Status</th>
                      <th className="px-6 py-4 font-medium whitespace-nowrap">Triggered By</th>
                      <th className="px-6 py-4 font-medium whitespace-nowrap">Updated</th>
                      <th className="px-6 py-4 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {filteredTasks.map((task) => {
                      const status = statusConfig[task.status as keyof typeof statusConfig] ?? {
                        icon: Clock,
                        color: 'bg-gray-400',
                        badgeVariant: 'outline' as const,
                        label: task.status || 'Unknown'
                      }
                      const StatusIcon = status.icon
                      const connector = getTaskConnector(task)
                      const connectorMeta = connectorConfig[connector.name as keyof typeof connectorConfig]
                      const ConnectorIcon = connectorMeta?.icon || User
                      return (
                        <tr key={task.id} className="hover:bg-muted/10 transition-colors group">
                          <td className="px-6 py-4 max-w-[250px] sm:max-w-[300px] lg:max-w-[500px]">
                            <div className="font-medium text-foreground mb-1 truncate">{task.name}</div>
                            {task.description && (
                              <div className="text-muted-foreground text-xs line-clamp-1">{task.description}</div>
                            )}
                            {task.parameters?.prompt && (
                              <div className="mt-2 bg-muted/30 rounded-md p-2 text-xs text-muted-foreground border border-border/50 line-clamp-3" title={task.parameters.prompt}>
                                <span className="font-semibold text-foreground/70 mr-1">Prompt:</span>
                                {task.parameters.prompt}
                              </div>
                            )}
                            <div className="text-muted-foreground text-[10px] font-mono mt-2 opacity-50 group-hover:opacity-100 transition-opacity">
                              #{task.id.slice(0, 8)}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <Badge variant={status.badgeVariant} className="font-medium whitespace-nowrap shadow-sm">
                              <StatusIcon className="w-3 h-3 mr-1.5" />
                              {status.label}
                            </Badge>
                          </td>
                          <td className="px-6 py-4">
                            {connector.name ? (
                              <div className="flex flex-col gap-0.5">
                                <div className={`flex items-center gap-1.5 text-xs font-medium ${connectorMeta?.color || 'text-muted-foreground'}`}>
                                  <ConnectorIcon className="w-3 h-3" />
                                  {connectorMeta?.label || connector.name}
                                </div>
                                {connector.user_email && (
                                  <div className="text-[10px] text-muted-foreground/70 truncate max-w-[140px]" title={connector.user_email}>
                                    {connector.user_email}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground/50">—</span>
                            )}
                          </td>
                          <td className="px-6 py-4 text-muted-foreground whitespace-nowrap">
                            {formatDate(task.updated_at)}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-2 opacity-50 group-hover:opacity-100 transition-opacity">
                              <Button size="sm" variant="ghost" className="h-8" onClick={() => handleViewLogs(task.id)}>
                                <FileText className="w-4 h-4 mr-1.5" /> Logs
                              </Button>
                              
                              {(task.status === 'running' || task.status === 'pending') && (
                                <Button size="sm" variant="ghost" className="h-8 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30" onClick={() => handleCancelTask(task.id)}>
                                  <X className="w-4 h-4 mr-1.5" /> Cancel
                                </Button>
                              )}
                              
                              {(task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') && (
                                <Button size="sm" variant="ghost" className="h-8" onClick={() => handleViewResult(task.id)}>
                                  <BarChart3 className="w-4 h-4 mr-1.5" /> Result
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-16 text-muted-foreground">
                <Activity className="w-12 h-12 mx-auto mb-4 opacity-20" />
                <h3 className="text-lg font-medium mb-1">No tasks found</h3>
                <p className="text-sm">Try adjusting your filters or search query.</p>
              </div>
            )}
            
            {/* Pagination Footer */}
            {(currentPage > 1 || filteredTasks.length > 0) && (
              <div className="p-4 border-t border-border/50 bg-muted/10 flex justify-center">
                <Pagination
                  currentPage={currentPage}
                  onPageChange={setCurrentPage}
                  currentDataSize={tasks.length}
                  itemsPerPage={itemsPerPage}
                />
              </div>
            )}
          </CardContent>
        </Card>

        <TaskResultModal
          open={resultModalOpen}
          onOpenChange={setResultModalOpen}
          taskId={selectedTaskId}
        />
      </div>
    </div>
  )
}
