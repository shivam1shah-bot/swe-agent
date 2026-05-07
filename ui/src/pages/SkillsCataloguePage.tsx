/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Search, Play, Clock } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { apiClient } from '@/lib/api'

interface Skill {
  name: string
  description: string
}

// ---------------------------------------------------------------------------
// Cron builder helpers
// ---------------------------------------------------------------------------

type FrequencyType = 'hourly' | 'daily' | 'weekly' | 'monthly' | 'custom'

interface CronBuilder {
  frequency: FrequencyType
  minuteOfHour: number   // used by all frequencies as the minute component
  hourOfDay: number      // daily / weekly / monthly
  dayOfWeek: number      // 0=Sun, 1=Mon ... 6=Sat
  dayOfMonth: number
  customCron: string
}

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

function pad(n: number) { return n.toString().padStart(2, '0') }

function builderToCron(b: CronBuilder): string {
  const m = b.minuteOfHour
  switch (b.frequency) {
    case 'hourly':  return `${m} * * * *`
    case 'daily':   return `${m} ${b.hourOfDay} * * *`
    case 'weekly':  return `${m} ${b.hourOfDay} * * ${b.dayOfWeek}`
    case 'monthly': return `${m} ${b.hourOfDay} ${b.dayOfMonth} * *`
    case 'custom':  return b.customCron
  }
}

function cronToHuman(b: CronBuilder): string {
  const time = `${pad(b.hourOfDay)}:${pad(b.minuteOfHour)}`
  switch (b.frequency) {
    case 'hourly':  return `Every hour at :${pad(b.minuteOfHour)}`
    case 'daily':   return `Every day at ${time}`
    case 'weekly':  return `Every ${DAY_NAMES[b.dayOfWeek]} at ${time}`
    case 'monthly': return `On day ${b.dayOfMonth} of every month at ${time}`
    case 'custom':  return b.customCron || '—'
  }
}

const DEFAULT_CRON_BUILDER: CronBuilder = {
  frequency: 'daily',
  minuteOfHour: 0,
  hourOfDay: 9,
  dayOfWeek: 1,
  dayOfMonth: 1,
  customCron: '',
}

interface ScheduleConfig {
  prompt: string
  cronExpression: string
  cronBuilder: CronBuilder
  runAt: string
  mode: 'once' | 'recurring'
  slackThread?: string
}


export function SkillsCataloguePage() {
  const navigate = useNavigate()
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  // Schedule modal state
  const [scheduleSkill, setScheduleSkill] = useState<Skill | null>(null)
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>({
    prompt: '',
    cronExpression: '',
    cronBuilder: DEFAULT_CRON_BUILDER,
    runAt: '',
    mode: 'once',
  })
  const [scheduling, setScheduling] = useState(false)
  const [scheduleResult, setScheduleResult] = useState<{ task_id?: string; status: string } | null>(null)
  const [scheduleError, setScheduleError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const data = await apiClient.listAgentSkills()
        setSkills(data)
      } catch (e: any) {
        setError(e.message || 'Failed to load skills')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = skills.filter(s =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.description.toLowerCase().includes(search.toLowerCase())
  )

  const handleRun = (skill: Skill) => {
    navigate(`/autonomous-agent?tab=clean-slate&skill=${encodeURIComponent(skill.name)}`)
  }

  const openSchedule = (skill: Skill) => {
    setScheduleSkill(skill)
    setScheduleConfig({ prompt: '', cronExpression: '', cronBuilder: DEFAULT_CRON_BUILDER, runAt: '', mode: 'once', slackThread: '' })
    setScheduleResult(null)
    setScheduleError(null)
  }

  const closeSchedule = () => {
    setScheduleSkill(null)
    setScheduleResult(null)
    setScheduleError(null)
  }

  const handleScheduleSubmit = async () => {
    if (!scheduleSkill) return

    setScheduling(true)
    setScheduleError(null)
    setScheduleResult(null)

    try {
      if (scheduleConfig.mode === 'recurring') {
        // Derive cron expression from the human-readable builder
        const cron = builderToCron(scheduleConfig.cronBuilder)
        if (!cron.trim()) {
          setScheduleError('Please configure a schedule frequency')
          return
        }
        const parameters: Record<string, any> = {
          prompt: scheduleConfig.prompt.trim(),
        }
        if (scheduleConfig.slackThread?.trim()) {
          parameters.slack_channel = scheduleConfig.slackThread.trim().replace(/^#/, '')
        }
        const schedule = await apiClient.createSchedule({
          name: `${scheduleSkill.name} — scheduled`,
          skill_name: scheduleSkill.name,
          cron_expression: cron,
          parameters,
        })
        setScheduleResult({ status: 'scheduled', task_id: schedule.id })
      } else {
        // One-off run — trigger immediately via agents/run
        const result = await apiClient.triggerCleanSlateAgent(
          scheduleConfig.prompt.trim(),
          [scheduleSkill.name],
          scheduleConfig.slackThread?.trim() || undefined
        )
        setScheduleResult(result)
      }
    } catch (e: any) {
      setScheduleError(e.message || 'Failed to schedule task')
    } finally {
      setScheduling(false)
    }
  }

  const formatSkillName = (name: string) =>
    name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />

      <div className="relative z-10 max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-violet-500" />
              Skills Catalogue
            </h1>
            <p className="text-muted-foreground mt-1">Discover and run available agent skills</p>
          </div>
          <div className="text-sm text-muted-foreground">
            {filtered.length} of {skills.length} skills
          </div>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search skills..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-red-700 dark:text-red-300">{error}</p>
          </div>
        )}

        {/* Skills Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(skill => (
            <Card key={skill.name} className="flex flex-col hover:shadow-md transition-shadow">
              <CardContent className="p-5 flex flex-col gap-3 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="h-8 w-8 rounded-lg bg-violet-100 dark:bg-violet-950 flex items-center justify-center shrink-0">
                      <Sparkles className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                    </div>
                    <h3 className="font-semibold text-sm leading-tight truncate">
                      {formatSkillName(skill.name)}
                    </h3>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground line-clamp-3 flex-1">
                  {skill.description || 'No description available.'}
                </p>

                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    className="flex-1 gap-1"
                    onClick={() => handleRun(skill)}
                  >
                    <Play className="h-3 w-3" />
                    Run
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 gap-1"
                    onClick={() => openSchedule(skill)}
                  >
                    <Clock className="h-3 w-3" />
                    Schedule
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}

          {filtered.length === 0 && !loading && (
            <div className="col-span-3 text-center py-16">
              <Sparkles className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No skills found matching your search</p>
            </div>
          )}
        </div>
      </div>

      {/* Schedule Modal */}
      <Dialog open={!!scheduleSkill} onOpenChange={open => !open && closeSchedule()}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-violet-500" />
              Schedule: {scheduleSkill ? formatSkillName(scheduleSkill.name) : ''}
            </DialogTitle>
          </DialogHeader>

          {scheduleResult ? (
            <div className="p-4 space-y-3">
              <div className="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-4">
                <p className="text-green-700 dark:text-green-300 font-medium">
                  {scheduleResult.status === 'scheduled'
                    ? 'Recurring schedule saved successfully'
                    : 'Task queued successfully'}
                </p>
                {scheduleResult.task_id && (
                  <p className="text-sm text-green-600 dark:text-green-400 mt-1">
                    {scheduleResult.status === 'scheduled' ? 'Schedule' : 'Task'} ID:{' '}
                    <code className="font-mono">{scheduleResult.task_id}</code>
                  </p>
                )}
              </div>
              <Button variant="outline" className="w-full" onClick={closeSchedule}>
                Close
              </Button>
            </div>
          ) : (
            <>
            <div className="p-6 space-y-5">
              {/* Mode toggle */}
              <div className="inline-flex bg-slate-100 dark:bg-slate-900 p-1 rounded-lg">
                <button
                  className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                    scheduleConfig.mode === 'once'
                      ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                  onClick={() => setScheduleConfig(c => ({ ...c, mode: 'once' }))}
                >
                  Run Once
                </button>
                <button
                  className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                    scheduleConfig.mode === 'recurring'
                      ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                  onClick={() => setScheduleConfig(c => ({ ...c, mode: 'recurring' }))}
                >
                  Recurring
                </button>
              </div>

              {/* Task prompt */}
              <div>
                <label className="block text-sm font-medium mb-1">Task description <span className="text-xs text-muted-foreground font-normal">(optional — skill will run with its default behaviour if left empty)</span></label>
                <textarea
                  className="w-full border border-slate-200 dark:border-slate-800 rounded-lg p-3 text-sm min-h-[100px] bg-white dark:bg-slate-950 resize-none focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 transition-all placeholder:text-slate-400"
                  placeholder={`Describe what you want the ${scheduleSkill ? formatSkillName(scheduleSkill.name) : 'skill'} to do...`}
                  value={scheduleConfig.prompt}
                  onChange={e => setScheduleConfig(c => ({ ...c, prompt: e.target.value }))}
                />
              </div>

              {/* Slack Channel */}
              <div>
                <label className="block text-sm font-medium mb-1">
                  Post result to Slack channel
                  <span className="ml-1 text-xs text-muted-foreground font-normal">(optional)</span>
                </label>
                <Input
                  placeholder="#channel-name"
                  value={scheduleConfig.slackThread ?? ''}
                  onChange={e => setScheduleConfig(c => ({ ...c, slackThread: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  The result will be posted to this channel using the Slack bot when done
                </p>
              </div>

              {scheduleConfig.mode === 'once' && (
                <div>
                  <label className="block text-sm font-medium mb-1">Run at</label>
                  <Input
                    type="datetime-local"
                    value={scheduleConfig.runAt}
                    onChange={e => setScheduleConfig(c => ({ ...c, runAt: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Leave empty to run immediately</p>
                </div>
              )}

              {scheduleConfig.mode === 'recurring' && (
                <div className="space-y-3">
                  <label className="block text-sm font-medium">Frequency</label>

                  {/* Frequency selector */}
                  <div className="flex flex-wrap gap-2">
                    {(['hourly', 'daily', 'weekly', 'monthly', 'custom'] as FrequencyType[]).map(f => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => setScheduleConfig(c => ({ ...c, cronBuilder: { ...c.cronBuilder, frequency: f } }))}
                        className={`px-3 py-1.5 text-sm rounded-md border transition-all capitalize ${scheduleConfig.cronBuilder.frequency === f ? 'bg-violet-500 text-white border-violet-500' : 'border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:border-violet-500/50'}`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>

                  {/* Frequency-specific inputs */}
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-3 space-y-3">
                    {/* Time picker for daily / weekly / monthly */}
                    {(scheduleConfig.cronBuilder.frequency === 'daily' || scheduleConfig.cronBuilder.frequency === 'weekly' || scheduleConfig.cronBuilder.frequency === 'monthly') && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Time</label>
                        <Input
                          type="time"
                          className="mt-1"
                          value={`${pad(scheduleConfig.cronBuilder.hourOfDay)}:${pad(scheduleConfig.cronBuilder.minuteOfHour)}`}
                          onChange={e => {
                            const [h, m] = (e.target.value || '09:00').split(':').map(Number)
                            setScheduleConfig(c => ({ ...c, cronBuilder: { ...c.cronBuilder, hourOfDay: h, minuteOfHour: m } }))
                          }}
                        />
                      </div>
                    )}

                    {/* Minute-past-the-hour for hourly */}
                    {scheduleConfig.cronBuilder.frequency === 'hourly' && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">At minute past the hour (0–59)</label>
                        <div className="flex items-center gap-2 mt-1">
                          <input
                            type="number"
                            min={0}
                            max={59}
                            className="w-20 border border-slate-200 dark:border-slate-800 rounded-md px-3 py-1.5 text-sm bg-white dark:bg-slate-950"
                            value={scheduleConfig.cronBuilder.minuteOfHour}
                            onChange={e => {
                              const v = Math.min(59, Math.max(0, +e.target.value || 0))
                              setScheduleConfig(c => ({ ...c, cronBuilder: { ...c.cronBuilder, minuteOfHour: v } }))
                            }}
                          />
                          <span className="text-xs text-muted-foreground">e.g. 30 → fires at :30 every hour</span>
                        </div>
                      </div>
                    )}

                    {scheduleConfig.cronBuilder.frequency === 'weekly' && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">On day</label>
                        <select
                          className="w-full mt-1 border border-slate-200 dark:border-slate-800 rounded-md px-3 py-1.5 text-sm bg-white dark:bg-slate-950"
                          value={scheduleConfig.cronBuilder.dayOfWeek}
                          onChange={e => setScheduleConfig(c => ({ ...c, cronBuilder: { ...c.cronBuilder, dayOfWeek: +e.target.value } }))}
                        >
                          {DAY_NAMES.map((d, i) => <option key={i} value={i}>{d}</option>)}
                        </select>
                      </div>
                    )}

                    {scheduleConfig.cronBuilder.frequency === 'monthly' && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">On day of month</label>
                        <select
                          className="w-full mt-1 border border-slate-200 dark:border-slate-800 rounded-md px-3 py-1.5 text-sm bg-white dark:bg-slate-950"
                          value={scheduleConfig.cronBuilder.dayOfMonth}
                          onChange={e => setScheduleConfig(c => ({ ...c, cronBuilder: { ...c.cronBuilder, dayOfMonth: +e.target.value } }))}
                        >
                          {Array.from({ length: 31 }, (_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}
                        </select>
                      </div>
                    )}

                    {scheduleConfig.cronBuilder.frequency === 'custom' && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Cron expression</label>
                        <Input
                          className="mt-1 font-mono text-sm"
                          placeholder="0 9 * * 1-5"
                          value={scheduleConfig.cronBuilder.customCron}
                          onChange={e => setScheduleConfig(c => ({ ...c, cronBuilder: { ...c.cronBuilder, customCron: e.target.value } }))}
                        />
                      </div>
                    )}

                    {/* Human-readable summary + cron preview */}
                    <div className="pt-1 border-t border-slate-200 dark:border-slate-700">
                      <p className="text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">Runs:</span> {cronToHuman(scheduleConfig.cronBuilder)}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5">
                        cron: <span className="text-violet-500">{builderToCron(scheduleConfig.cronBuilder)}</span>
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {scheduleError && (
                <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-3">
                  <p className="text-red-700 dark:text-red-300 text-sm">{scheduleError}</p>
                </div>
              )}
            </div>
            <DialogFooter className="px-6 py-4 border-t bg-slate-50/50 dark:bg-slate-900/50 rounded-b-lg">
              <Button variant="outline" onClick={closeSchedule} className="rounded-lg">Cancel</Button>
              <Button
                onClick={handleScheduleSubmit}
                disabled={scheduling}
                className="gap-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg"
              >
                {scheduling ? (
                  <><div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" /> Queuing...</>
                ) : (
                  <><Clock className="h-4 w-4" /> Queue Task</>
                )}
              </Button>
            </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default SkillsCataloguePage
