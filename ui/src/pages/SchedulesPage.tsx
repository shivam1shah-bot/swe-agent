import { useState, useEffect, useCallback } from 'react'
import { Clock, Play, Trash2, RefreshCw, ToggleLeft, ToggleRight, Activity } from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { apiClient, Schedule } from '@/lib/api'

function cronToHuman(cron: string): string {
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return cron
  const [min, hour, dom, , dow] = parts
  if (min === '*' && hour === '*') return `Every minute`
  if (hour === '*') return `Every hour at :${min.padStart(2, '0')}`
  if (dom === '*' && dow === '*') return `Daily at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  if (dom === '*') {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    return `Every ${days[+dow] || dow} at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  }
  return cron
}

function formatTs(ts: number | null): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}

export function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [actionId, setActionId] = useState<string | null>(null)

  const load = useCallback(async (showSpinner = false) => {
    try {
      if (showSpinner) setRefreshing(true)
      const data = await apiClient.getSchedules()
      setSchedules(data)
    } catch (e) {
      console.error('Failed to load schedules', e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const toggle = async (s: Schedule) => {
    setActionId(s.id)
    try {
      const updated = await apiClient.updateSchedule(s.id, { enabled: !s.enabled })
      setSchedules(prev => prev.map(x => x.id === s.id ? updated : x))
    } catch (e) { console.error(e) }
    setActionId(null)
  }

  const trigger = async (s: Schedule) => {
    setActionId(s.id)
    try {
      await apiClient.triggerSchedule(s.id)
      await load()
    } catch (e) { console.error(e) }
    setActionId(null)
  }

  const remove = async (s: Schedule) => {
    if (!window.confirm(`Delete schedule "${s.name}"?`)) return
    setActionId(s.id)
    try {
      await apiClient.deleteSchedule(s.id)
      setSchedules(prev => prev.filter(x => x.id !== s.id))
    } catch (e) { console.error(e) }
    setActionId(null)
  }

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />

      <div className="relative z-10 max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 mt-2">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
              <Clock className="w-6 h-6 mr-2 text-violet-500" />
              Scheduled Tasks
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage and monitor recurring skill executions
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => load(true)} disabled={refreshing}>
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="h-9 w-9 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
                <Clock className="h-4 w-4 text-violet-600" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total</p>
                <p className="text-2xl font-bold">{schedules.length}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="h-9 w-9 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <Activity className="h-4 w-4 text-green-600" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Active</p>
                <p className="text-2xl font-bold">{schedules.filter(s => s.enabled).length}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="h-9 w-9 rounded-full bg-slate-100 dark:bg-slate-900/30 flex items-center justify-center">
                <ToggleLeft className="h-4 w-4 text-slate-500" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Paused</p>
                <p className="text-2xl font-bold">{schedules.filter(s => !s.enabled).length}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Table */}
        <Card className="shadow-sm border-border/50">
          <CardHeader className="pb-3 border-b border-border/50">
            <p className="text-sm font-medium text-muted-foreground">
              {schedules.length} schedule{schedules.length !== 1 ? 's' : ''}
            </p>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-12 text-center text-muted-foreground">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-3 text-primary/50" />
                Loading schedules...
              </div>
            ) : schedules.length === 0 ? (
              <div className="p-12 text-center text-muted-foreground">
                <Clock className="w-10 h-10 mx-auto mb-3 opacity-20" />
                <p className="font-medium">No schedules yet</p>
                <p className="text-sm mt-1">Create one from the Skills Catalogue page.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-muted-foreground uppercase bg-muted/20 border-b border-border/50">
                    <tr>
                      <th className="px-6 py-3 font-medium">Schedule</th>
                      <th className="px-6 py-3 font-medium">Skill</th>
                      <th className="px-6 py-3 font-medium">Frequency</th>
                      <th className="px-6 py-3 font-medium">Last Run</th>
                      <th className="px-6 py-3 font-medium">Status</th>
                      <th className="px-6 py-3 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {schedules.map(s => (
                      <tr key={s.id} className="hover:bg-muted/10 transition-colors group">
                        {/* Name */}
                        <td className="px-6 py-4">
                          <div className="font-medium text-foreground">{s.name}</div>
                          <div className="text-[10px] font-mono text-muted-foreground/50 mt-0.5">
                            #{s.id}
                          </div>
                          {s.parameters?.slack_channel && (
                            <div className="text-xs text-muted-foreground mt-0.5">
                              → #{s.parameters.slack_channel}
                            </div>
                          )}
                        </td>

                        {/* Skill */}
                        <td className="px-6 py-4">
                          <Badge variant="secondary" className="font-mono text-xs">
                            {s.skill_name}
                          </Badge>
                        </td>

                        {/* Frequency */}
                        <td className="px-6 py-4">
                          <div className="text-foreground">{cronToHuman(s.cron_expression)}</div>
                          <div className="text-xs text-muted-foreground font-mono mt-0.5">{s.cron_expression}</div>
                        </td>

                        {/* Last Run */}
                        <td className="px-6 py-4 text-muted-foreground whitespace-nowrap">
                          {formatTs(s.last_run_at)}
                        </td>

                        {/* Status */}
                        <td className="px-6 py-4">
                          <Badge variant={s.enabled ? 'default' : 'outline'} className={s.enabled ? 'bg-green-500 text-white' : ''}>
                            {s.enabled ? 'Active' : 'Paused'}
                          </Badge>
                        </td>

                        {/* Actions */}
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                            {/* Toggle enable/disable */}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 gap-1.5"
                              disabled={actionId === s.id}
                              onClick={() => toggle(s)}
                              title={s.enabled ? 'Pause' : 'Enable'}
                            >
                              {s.enabled
                                ? <ToggleRight className="w-4 h-4 text-green-500" />
                                : <ToggleLeft className="w-4 h-4 text-muted-foreground" />}
                              {s.enabled ? 'Pause' : 'Enable'}
                            </Button>

                            {/* Trigger now */}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 gap-1.5"
                              disabled={actionId === s.id}
                              onClick={() => trigger(s)}
                              title="Run now"
                            >
                              <Play className="w-3.5 h-3.5" />
                              Run now
                            </Button>

                            {/* Delete */}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                              disabled={actionId === s.id}
                              onClick={() => remove(s)}
                              title="Delete"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
