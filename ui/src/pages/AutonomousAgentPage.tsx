/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Bot, Send, CheckCircle, RefreshCw, Gauge } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { apiClient } from '@/lib/api'

// ─── Rate limit types & hook ──────────────────────────────────────────────────

interface RateLimitStatus {
  used: number
  limit: number
  remaining: number
  window_seconds: number
  reset_in_seconds: number
}

function useRateLimitStatus() {
  const [data, setData] = useState<RateLimitStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await apiClient.get<RateLimitStatus>('/api/v1/agents/rate-limit-status')
      setData(res)
    } catch {
      // fail silently — rate limit display is informational only
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 30_000)
    return () => clearInterval(id)
  }, [refresh])

  return { data, loading, refresh }
}

// ─── Rate limit panel ─────────────────────────────────────────────────────────

function RateLimitPanel({ data, loading }: { data: RateLimitStatus | null; loading: boolean }) {
  if (loading || !data) return null

  const pct = Math.min((data.used / data.limit) * 100, 100)
  let color = 'bg-green-500'
  if (pct >= 90) color = 'bg-red-500'
  else if (pct >= 60) color = 'bg-yellow-500'

  return (
    <div className="mb-5 rounded-lg border border-border bg-muted/30 px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          <Gauge className="h-3.5 w-3.5" />
          Agent API Rate Limit · {data.limit} req / {data.window_seconds}s
        </div>
        <span className={`text-xs font-mono ${data.remaining === 0 ? 'text-red-500 font-semibold' : 'text-muted-foreground'}`}>
          {data.remaining}/{data.limit} remaining
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {data.remaining === 0 && (
        <p className="text-[11px] text-red-500 mt-1">
          Limit reached — resets in {data.reset_in_seconds}s
        </p>
      )}
    </div>
  )
}

const SKILLS_CACHE_TTL_MS = 5 * 60 * 1000 // 5 minutes

type ActiveTab = 'single' | 'batch' | 'multi-repo' | 'clean-slate'

interface Skill {
  name: string
  description: string
}

function parseBatchRepositories(
  text: string,
  maxRepos: number
): { repos: Array<{ repository_url: string; branch?: string }>; errors: string[] } {
  const lines = text
    .split(/[\n,]/)
    .map(l => l.trim())
    .filter(Boolean)
  const repos: Array<{ repository_url: string; branch?: string }> = []
  const errors: string[] = []

  if (lines.length > maxRepos) {
    errors.push(`Maximum ${maxRepos} repositories allowed; you entered ${lines.length}. Only the first ${maxRepos} will be considered.`)
  }

  lines.slice(0, maxRepos).forEach((line, idx) => {
    const [repoPart, branchPartRaw] = line.split('@')
    const repo = (repoPart || '').trim()
    const branchPart = (branchPartRaw || '').trim()

    if (!repo) {
      errors.push(`Line ${idx + 1}: repository name is required`)
      return
    }
    if (branchPart && (branchPart.toLowerCase() === 'main' || branchPart.toLowerCase() === 'master')) {
      errors.push(`Line ${idx + 1}: branches 'main' and 'master' are not allowed. Please use a different branch name.`)
      return
    }
    const entry: { repository_url: string; branch?: string } = {
      repository_url: `https://github.com/razorpay/${repo}`
    }
    if (branchPart) entry.branch = branchPart
    repos.push(entry)
  })

  return { repos, errors }
}

interface SkillsPanelProps {
  selectedSkills: string[]
  onSelectionChange: (skills: string[]) => void
}

function SkillsPanel({ selectedSkills, onSelectionChange }: SkillsPanelProps) {
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(false)
  const [skillsError, setSkillsError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const cacheRef = useRef<{ skills: Skill[]; expiry: number } | null>(null)

  const fetchSkills = async (force = false) => {
    if (!force && cacheRef.current && Date.now() < cacheRef.current.expiry) {
      setAvailableSkills(cacheRef.current.skills)
      return
    }
    setLoading(true)
    setSkillsError(null)
    try {
      const skills = await apiClient.listAgentSkills()
      cacheRef.current = { skills, expiry: Date.now() + SKILLS_CACHE_TTL_MS }
      setAvailableSkills(skills)
    } catch (_err) {
      setSkillsError('Failed to load skills. Click Refresh to try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSkills()
  }, [])

  const toggleSkill = (skillName: string) => {
    if (selectedSkills.includes(skillName)) {
      onSelectionChange(selectedSkills.filter(s => s !== skillName))
    } else {
      onSelectionChange([...selectedSkills, skillName])
    }
  }

  const selectedSkillObjects = availableSkills.filter(skill =>
    selectedSkills.includes(skill.name)
  )
  const filteredUnselectedSkills = availableSkills.filter(skill =>
    !selectedSkills.includes(skill.name) &&
    skill.name.toLowerCase().includes(search.toLowerCase())
  )

  const renderSkillRow = (skill: Skill, isSelected: boolean) => (
    <label key={skill.name} className={`flex items-start gap-2 cursor-pointer rounded px-1.5 py-1 transition-colors ${isSelected ? 'bg-primary/10' : 'hover:bg-accent/50'}`}>
      <input
        type="checkbox"
        className="mt-0.5"
        checked={isSelected}
        onChange={() => toggleSkill(skill.name)}
      />
      <span className="text-sm">
        <span className="font-medium text-foreground">{skill.name}</span>
        {skill.description && (
          <span className="text-muted-foreground ml-1">— {skill.description}</span>
        )}
      </span>
    </label>
  )

  return (
    <div className="border-t border-border pt-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-foreground">
          Skills
          {selectedSkills.length > 0 && (
            <span className="ml-1.5 text-xs font-normal text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">
              {selectedSkills.length} selected
            </span>
          )}
        </span>
        <button
          type="button"
          onClick={() => fetchSkills(true)}
          disabled={loading}
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {skillsError && (
        <p className="text-destructive text-xs mb-2">{skillsError}</p>
      )}
      {loading && availableSkills.length === 0 && (
        <p className="text-muted-foreground text-xs">Loading skills...</p>
      )}
      {!loading && availableSkills.length === 0 && !skillsError && (
        <p className="text-muted-foreground text-xs">No skills available.</p>
      )}
      {availableSkills.length > 0 && (
        <>
          <input
            type="text"
            placeholder="Search skills..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full text-xs bg-background/50 border border-input rounded px-2 py-1 mb-2 focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
          />
          <div className="max-h-48 overflow-y-auto pr-1">
            {selectedSkillObjects.length > 0 && (
              <div className="space-y-1 mb-2">
                {selectedSkillObjects.map(skill => renderSkillRow(skill, true))}
                {filteredUnselectedSkills.length > 0 && (
                  <div className="border-t border-border my-1.5" />
                )}
              </div>
            )}
            <div className="space-y-1">
              {filteredUnselectedSkills.length === 0 && selectedSkillObjects.length === 0 ? (
                <p className="text-muted-foreground text-xs px-1.5">No skills match your search.</p>
              ) : (
                filteredUnselectedSkills.map(skill => renderSkillRow(skill, false))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export function AutonomousAgentPage() {
  const navigate = useNavigate()
  const { data: rateLimits, loading: rlLoading, refresh: refreshRL } = useRateLimitStatus()
  const [isExecuting, setIsExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<ActiveTab>(
    (searchParams.get('tab') as ActiveTab) || 'single'
  )

  // Shared skills state (per-tab so selections are independent)
  const [singleSkills, setSingleSkills] = useState<string[]>([])
  const [batchSkills, setBatchSkills] = useState<string[]>([])
  const [multiRepoSkills, setMultiRepoSkills] = useState<string[]>([])
  const [cleanSlateSkills, setCleanSlateSkills] = useState<string[]>(() => {
    const skill = searchParams.get('skill')
    return skill ? [skill] : []
  })

  const [formData, setFormData] = useState({
    repositoryName: '',
    branchName: '',
    taskDescription: ''
  })

  const [batchData, setBatchData] = useState({
    repositoriesText: '',
    taskDescription: ''
  })
  const [batchParsedRepos, setBatchParsedRepos] = useState<Array<{ repository_url: string; branch?: string }>>([])
  const [batchErrors, setBatchErrors] = useState<string[]>([])

  const [multiRepoData, setMultiRepoData] = useState({
    repositoriesText: '',
    taskDescription: ''
  })
  const [multiRepoParsedRepos, setMultiRepoParsedRepos] = useState<Array<{ repository_url: string; branch?: string }>>([])
  const [multiRepoErrors, setMultiRepoErrors] = useState<string[]>([])

  const [cleanSlateData, setCleanSlateData] = useState({ taskDescription: '', slackChannel: '' })

  // Reset success/error when switching tabs
  const switchTab = (tab: ActiveTab) => {
    setActiveTab(tab)
    setError(null)
    setSuccess(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.repositoryName.trim()) {
      setError('Please enter a repository name.')
      return
    }

    if (!formData.taskDescription.trim()) {
      setError('Please enter a task description for the autonomous agent.')
      return
    }

    setIsExecuting(true)
    setError(null)
    setSuccess(false)

    try {
      const resp: any = await apiClient.triggerAutonomousAgent(
        formData.taskDescription.trim(),
        `https://github.com/razorpay/${formData.repositoryName.trim()}`,
        formData.branchName.trim() || undefined,
        singleSkills
      )
      if (resp && resp.status && resp.status.toLowerCase() === 'failed') {
        setError(resp.message || 'Validation failed')
      } else {
        setSuccess(true)
        setFormData({ repositoryName: '', branchName: '', taskDescription: '' })
        setSingleSkills([])
      }
    } catch (error) {
      console.error('Failed to start autonomous agent:', error)
      setError((error as Error).message || 'Error starting autonomous agent. Please try again.')
    } finally {
      setIsExecuting(false)
      refreshRL()
    }
  }

  const handleBatchSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!batchData.repositoriesText.trim()) {
      setError('Please enter at least one repository.')
      return
    }
    if (!batchData.taskDescription.trim()) {
      setError('Please enter a task description for the autonomous agent.')
      return
    }
    if (batchErrors.length > 0 || batchParsedRepos.length === 0) {
      setError('Please fix errors in the repository list before submitting.')
      return
    }

    setIsExecuting(true)
    setError(null)
    setSuccess(false)

    try {
      const resp: any = await apiClient.triggerAutonomousAgentBatch(
        batchData.taskDescription.trim(),
        batchParsedRepos,
        batchSkills
      )
      if (resp && resp.status && resp.status.toLowerCase() === 'failed') {
        setError(resp.message || 'Validation failed')
      } else {
        setSuccess(true)
        setBatchData({ repositoriesText: '', taskDescription: '' })
        setBatchParsedRepos([])
        setBatchErrors([])
        setBatchSkills([])
      }
    } catch (error) {
      console.error('Failed to start autonomous agent batch:', error)
      setError((error as Error).message || 'Error starting batch autonomous agent. Please try again.')
    } finally {
      setIsExecuting(false)
      refreshRL()
    }
  }

  const handleMultiRepoSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!multiRepoData.repositoriesText.trim()) {
      setError('Please enter at least 2 repositories.')
      return
    }
    if (!multiRepoData.taskDescription.trim()) {
      setError('Please enter a task description.')
      return
    }
    if (multiRepoErrors.length > 0) {
      setError('Please fix errors in the repository list before submitting.')
      return
    }
    if (multiRepoParsedRepos.length < 2) {
      setError('Multi-repo requires at least 2 repositories.')
      return
    }
    if (multiRepoParsedRepos.length > 10) {
      setError('Multi-repo supports a maximum of 10 repositories.')
      return
    }

    setIsExecuting(true)
    setError(null)
    setSuccess(false)

    try {
      const resp: any = await apiClient.triggerMultiRepoAgent(
        multiRepoData.taskDescription.trim(),
        multiRepoParsedRepos,
        multiRepoSkills
      )
      if (resp && resp.status && resp.status.toLowerCase() === 'failed') {
        setError(resp.message || 'Validation failed')
      } else {
        setSuccess(true)
        setMultiRepoData({ repositoriesText: '', taskDescription: '' })
        setMultiRepoParsedRepos([])
        setMultiRepoErrors([])
        setMultiRepoSkills([])
      }
    } catch (error) {
      console.error('Failed to start multi-repo autonomous agent:', error)
      setError((error as Error).message || 'Error starting multi-repo agent. Please try again.')
    } finally {
      setIsExecuting(false)
      refreshRL()
    }
  }

  const handleCleanSlateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const hasPrompt = cleanSlateData.taskDescription.trim().length > 0
    const hasSkills = cleanSlateSkills.length > 0

    if (!hasPrompt && !hasSkills) {
      setError('Please enter a task description or select at least one skill.')
      return
    }

    setIsExecuting(true)
    setError(null)
    setSuccess(false)

    try {
      const resp: any = await apiClient.triggerCleanSlateAgent(
        cleanSlateData.taskDescription.trim(),
        cleanSlateSkills,
        cleanSlateData.slackChannel.trim() || undefined
      )
      if (resp && resp.status && resp.status.toLowerCase() === 'failed') {
        setError(resp.message || 'Validation failed')
      } else {
        setSuccess(true)
        setCleanSlateData({ taskDescription: '', slackChannel: '' })
        setCleanSlateSkills([])
      }
    } catch (error) {
      console.error('Failed to start clean slate autonomous agent:', error)
      setError((error as Error).message || 'Error starting clean slate agent. Please try again.')
    } finally {
      setIsExecuting(false)
      refreshRL()
    }
  }

  const successBanner = (message: string) => (
    <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-900/50 rounded-lg p-4">
      <div className="flex items-center mb-2">
        <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-500 mr-2" />
        <span className="text-green-700 dark:text-green-400 font-medium">{message}</span>
      </div>
      <p className="text-green-700 dark:text-green-400 text-sm">
        Monitor progress in the{' '}
        <button
          onClick={() => navigate('/tasks')}
          className="underline hover:text-green-800 dark:hover:text-green-300 font-medium"
        >
          Tasks page
        </button>
        .
      </p>
    </div>
  )

  const errorBanner = error ? (
    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/50 rounded-lg p-4">
      <p className="text-red-700 dark:text-red-400 text-sm">{error}</p>
    </div>
  ) : null

  const tabButton = (tab: ActiveTab, label: string) => (
    <button
      className={`px-4 py-2 rounded-md border text-sm font-medium transition-colors ${
        activeTab === tab 
          ? 'bg-background/80 border-border shadow-sm text-foreground' 
          : 'bg-muted/30 border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground'
      }`}
      onClick={() => switchTab(tab)}
      type="button"
    >
      {label}
    </button>
  )

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />
      
      <div className="relative z-10 max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6 mt-2">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
            <Bot className="w-6 h-6 mr-2 text-blue-600" />
            Autonomous Agent
          </h1>
          <p className="text-muted-foreground mt-1">
            Coding tasks — Execute complex tasks using intelligent autonomous agents with tool integration and error recovery.
          </p>
        </div>

        {/* Rate limit panel */}
        <RateLimitPanel data={rateLimits} loading={rlLoading} />

        {/* Main Content */}
        <div>
        {/* Tabs */}
        <div className="mb-4 flex gap-2">
          {tabButton('single', 'Single')}
          {tabButton('batch', 'Batch')}
          {tabButton('multi-repo', 'Multi-Repo')}
          {tabButton('clean-slate', 'Clean Slate')}
        </div>

        {/* Single Tab */}
        {activeTab === 'single' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle>Repository</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Organization</label>
                    <div className="w-full p-2 border border-border rounded-md bg-muted/30 text-muted-foreground">
                      razorpay
                    </div>
                  </div>

                  <div>
                    <label className="text-sm font-medium">Repository Name <span className="text-red-500">*</span></label>
                    <Input
                      placeholder="e.g., scrooge, pg-router"
                      value={formData.repositoryName}
                      onChange={(e) => setFormData(prev => ({ ...prev, repositoryName: e.target.value }))}
                      required
                    />
                    <div className="text-sm text-gray-500 mt-1">Enter the repository name (without organization prefix)</div>
                  </div>

                  <div>
                    <label className="text-sm font-medium">Branch Name (optional)</label>
                    <Input
                      placeholder="feature-branch"
                      value={formData.branchName}
                      onChange={(e) => setFormData(prev => ({ ...prev, branchName: e.target.value }))}
                    />
                    <div className="text-sm text-gray-500 mt-1">If not provided, the agent will create a new branch.</div>
                    {(formData.branchName.trim().toLowerCase() === 'main' || formData.branchName.trim().toLowerCase() === 'master') && (
                      <div className="mt-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/50 text-red-700 dark:text-red-400 text-sm rounded-md p-2">
                        Branches 'main' and 'master' are not allowed at Razorpay. Please use a different branch name.
                      </div>
                    )}
                  </div>

                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/50 rounded-lg p-3">
                    <p className="text-yellow-800 dark:text-yellow-400 text-sm">
                      <strong>Note:</strong> This autonomous agent only works with Razorpay private repositories.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Task</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label htmlFor="taskDescription" className="block text-sm font-medium mb-2">
                      Task Description <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      id="taskDescription"
                      value={formData.taskDescription}
                      onChange={(e) => setFormData(prev => ({ ...prev, taskDescription: e.target.value }))}
                      rows={5}
                      className="w-full px-3 py-2 border border-input bg-background/50 rounded-md focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                      placeholder="Describe the task you want the autonomous agent to perform."
                      required
                    />
                  </div>

                  <SkillsPanel selectedSkills={singleSkills} onSelectionChange={setSingleSkills} />

                  {success && successBanner('Autonomous agent started successfully!')}
                  {errorBanner}

                  <Button
                    onClick={handleSubmit}
                    disabled={!formData.repositoryName.trim() || !formData.taskDescription.trim() || isExecuting || formData.branchName.trim().toLowerCase() === 'main' || formData.branchName.trim().toLowerCase() === 'master'}
                    className="w-full flex items-center justify-center"
                  >
                    <Send className="w-4 h-4 mr-2" />
                    {isExecuting ? 'Starting Autonomous Agent...' : '🤖 Start Autonomous Agent'}
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Batch Tab */}
        {activeTab === 'batch' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle>Repositories</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Organization</label>
                    <div className="w-full p-2 border border-border rounded-md bg-muted/30 text-muted-foreground">razorpay</div>
                  </div>

                  <div>
                    <label className="text-sm font-medium">Repositories List <span className="text-red-500">*</span></label>
                    <textarea
                      rows={8}
                      className="w-full px-3 py-2 border border-input bg-background/50 rounded-md focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                      placeholder={`Comma separated. Examples: scrooge, pg-router@feature-branch`}
                      value={batchData.repositoriesText}
                      onChange={(e) => {
                        const value = e.target.value
                        setBatchData(prev => ({ ...prev, repositoriesText: value }))
                        const { repos, errors } = parseBatchRepositories(value, 50)
                        setBatchParsedRepos(repos)
                        setBatchErrors(errors)
                      }}
                    />
                    <div className="text-sm text-gray-500 mt-1">
                      Up to 50 entries. Use <code>repo</code> or <code>repo@branch</code>. Branches 'main' and 'master' are not allowed.
                    </div>
                  </div>

                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/50 rounded-lg p-3">
                    <p className="text-yellow-800 dark:text-yellow-400 text-sm">
                      <strong>Note:</strong> Only works with Razorpay private repositories.
                    </p>
                  </div>

                  {batchErrors.length > 0 && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/50 rounded-lg p-3">
                      <ul className="list-disc list-inside text-red-700 dark:text-red-400 text-sm">
                        {batchErrors.map((err, i) => <li key={i}>{err}</li>)}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Task</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Task Description <span className="text-red-500">*</span></label>
                    <textarea
                      rows={5}
                      className="w-full px-3 py-2 border border-input bg-background/50 rounded-md focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                      placeholder="Describe the changes you want applied across all selected repositories."
                      value={batchData.taskDescription}
                      onChange={(e) => setBatchData(prev => ({ ...prev, taskDescription: e.target.value }))}
                      required
                    />
                  </div>

                  <SkillsPanel selectedSkills={batchSkills} onSelectionChange={setBatchSkills} />

                  {success && successBanner('Batch autonomous agent started successfully!')}
                  {errorBanner}

                  <Button
                    onClick={handleBatchSubmit}
                    disabled={isExecuting || !batchData.taskDescription.trim() || batchParsedRepos.length === 0 || batchErrors.length > 0}
                    className="w-full flex items-center justify-center"
                  >
                    <Send className="w-4 h-4 mr-2" />
                    {isExecuting ? 'Starting Batch...' : '🚀 Start Batch'}
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Multi-Repo Tab */}
        {activeTab === 'multi-repo' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle>Repositories</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Organization</label>
                    <div className="w-full p-2 border border-border rounded-md bg-muted/30 text-muted-foreground">razorpay</div>
                  </div>

                  <div>
                    <label className="text-sm font-medium">Repositories (2–10) <span className="text-red-500">*</span></label>
                    <textarea
                      rows={6}
                      className="w-full px-3 py-2 border border-input bg-background/50 rounded-md focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                      placeholder={`2–10 repos. Examples:\nscrooge\npg-router@feature-branch`}
                      value={multiRepoData.repositoriesText}
                      onChange={(e) => {
                        const value = e.target.value
                        setMultiRepoData(prev => ({ ...prev, repositoriesText: value }))
                        const { repos, errors } = parseBatchRepositories(value, 10)
                        setMultiRepoParsedRepos(repos)
                        const allErrors = [...errors]
                        if (repos.length > 0 && repos.length < 2) {
                          allErrors.push('Multi-repo requires at least 2 repositories.')
                        }
                        setMultiRepoErrors(allErrors)
                      }}
                    />
                    <div className="text-sm text-gray-500 mt-1">
                      2–10 repos. One sub-agent per service, all working in context of each other.
                    </div>
                  </div>

                  <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-900/50 rounded-lg p-3">
                    <p className="text-blue-800 dark:text-blue-400 text-sm">
                      <strong>Multi-Repo:</strong> Designed for microservice and distributed system tasks. Each repo gets a dedicated sub-agent that understands the broader system context — ideal for cross-service changes, shared contracts, or coordinated refactors.
                    </p>
                  </div>

                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/50 rounded-lg p-3">
                    <p className="text-yellow-800 dark:text-yellow-400 text-sm">
                      <strong>Note:</strong> Only works with Razorpay private repositories.
                    </p>
                  </div>

                  {multiRepoErrors.length > 0 && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/50 rounded-lg p-3">
                      <ul className="list-disc list-inside text-red-700 dark:text-red-400 text-sm">
                        {multiRepoErrors.map((err, i) => <li key={i}>{err}</li>)}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Task</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Task Description <span className="text-red-500">*</span></label>
                    <textarea
                      rows={5}
                      className="w-full px-3 py-2 border border-input bg-background/50 rounded-md focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                      placeholder="Describe the task in terms of the overall system. e.g. 'Add a new payment method that requires changes to the API gateway, payment service, and notification service.'"
                      value={multiRepoData.taskDescription}
                      onChange={(e) => setMultiRepoData(prev => ({ ...prev, taskDescription: e.target.value }))}
                      required
                    />
                  </div>

                  <SkillsPanel selectedSkills={multiRepoSkills} onSelectionChange={setMultiRepoSkills} />

                  {success && successBanner('Multi-repo agent started — sub-agents are coordinating across services.')}
                  {errorBanner}

                  <Button
                    onClick={handleMultiRepoSubmit}
                    disabled={
                      isExecuting ||
                      !multiRepoData.taskDescription.trim() ||
                      multiRepoParsedRepos.length < 2 ||
                      multiRepoParsedRepos.length > 10 ||
                      multiRepoErrors.length > 0
                    }
                    className="w-full flex items-center justify-center"
                  >
                    <Send className="w-4 h-4 mr-2" />
                    {isExecuting ? 'Starting Multi-Repo Agent...' : '🤝 Start Multi-Repo Agent'}
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Clean Slate Tab */}
        {activeTab === 'clean-slate' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle>Workspace</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-900/50 rounded-lg p-3">
                    <p className="text-purple-800 dark:text-purple-400 text-sm">
                      <strong>Clean Slate:</strong> The agent works in a fresh temp directory with no repository. Files are created from scratch. No git push is performed.
                    </p>
                  </div>
                  <div className="w-full p-2 border border-border rounded-md bg-muted/30 text-muted-foreground text-sm">
                    No repository required — agent creates files in a temp workspace.
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Clean Slate Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label htmlFor="cleanSlateTask" className="block text-sm font-medium mb-2">
                      Task Description <span className="text-muted-foreground text-xs font-normal">(optional if a skill is selected)</span>
                    </label>
                    <textarea
                      id="cleanSlateTask"
                      value={cleanSlateData.taskDescription}
                      onChange={(e) => setCleanSlateData(prev => ({ ...prev, taskDescription: e.target.value }))}
                      rows={6}
                      className="w-full px-3 py-2 border border-input bg-background/50 rounded-md focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                      placeholder="Describe what you want the agent to create or build. Leave blank if the selected skill defines the task."
                    />
                    <div className="text-xs text-muted-foreground mt-2">
                      Examples: Generate a report, create a scaffold project, produce documentation, run analysis scripts.
                    </div>
                  </div>

                  <div>
                    <label htmlFor="cleanSlateSlack" className="block text-sm font-medium mb-2">
                      Post result to Slack channel <span className="text-muted-foreground text-xs font-normal">(optional)</span>
                    </label>
                    <Input
                      id="cleanSlateSlack"
                      value={cleanSlateData.slackChannel}
                      onChange={(e) => setCleanSlateData(prev => ({ ...prev, slackChannel: e.target.value }))}
                      placeholder="#channel-name"
                    />
                    <div className="text-xs text-muted-foreground mt-1">
                      When done, the agent's output will be posted to this channel.
                    </div>
                  </div>

                  <SkillsPanel selectedSkills={cleanSlateSkills} onSelectionChange={setCleanSlateSkills} />

                  {success && successBanner('Clean slate agent started successfully!')}
                  {errorBanner}

                  <Button
                    onClick={handleCleanSlateSubmit}
                    disabled={isExecuting || (!cleanSlateData.taskDescription.trim() && cleanSlateSkills.length === 0)}
                    className="w-full flex items-center justify-center"
                  >
                    <Send className="w-4 h-4 mr-2" />
                    {isExecuting ? 'Starting Clean Slate Agent...' : '✨ Start Clean Slate Agent'}
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
    </div>
  )
}
