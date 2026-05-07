import { useState, useEffect, useCallback } from 'react'
import { Settings, Github, Slack, Globe, User, RefreshCw, CheckCircle, AlertCircle, Link, Gauge } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/api'

// ─── Rate limit types & panel ─────────────────────────────────────────────────

interface RateLimitStatus {
  used: number
  limit: number
  remaining: number
  window_seconds: number
  reset_in_seconds: number
}

function RateLimitCard() {
  const [data, setData] = useState<RateLimitStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await apiClient.get<RateLimitStatus>('/api/v1/agents/rate-limit-status')
      setData(res)
    } catch {
      // fail silently
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 30_000)
    return () => clearInterval(id)
  }, [refresh])

  const pct = data ? Math.min((data.used / data.limit) * 100, 100) : 0
  let barColor = 'bg-green-500'
  if (pct >= 90) barColor = 'bg-red-500'
  else if (pct >= 60) barColor = 'bg-yellow-500'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-slate-500" />
          Agent API Rate Limit
        </CardTitle>
        <CardDescription>
          Your usage of the autonomous agent API within the current time window
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            <div className="h-4 w-48 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
          </div>
        ) : data ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {data.limit} requests / {data.window_seconds}s window
              </span>
              <span className={`font-mono font-medium ${data.remaining === 0 ? 'text-red-500' : 'text-foreground'}`}>
                {data.used} / {data.limit} used
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{data.remaining} remaining</span>
              <span>Resets in {data.reset_in_seconds}s</span>
            </div>
            {data.remaining === 0 && (
              <p className="text-xs text-red-500 font-medium">
                Rate limit reached — resets in {data.reset_in_seconds}s
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Unable to load rate limit data.</p>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface SlackIdentity     { handle?: string; user_id?: string }
interface GithubIdentity    { username: string }
interface DevRevIdentity    { email: string }
interface DashboardIdentity { username: string }

interface UserProfile {
  email: string | null
  display_name: string | null
  identities: {
    dashboard?: DashboardIdentity
    slack?:     SlackIdentity
    github?:    GithubIdentity
    devrev?:    DevRevIdentity
  }
}

// ─── Platform config ──────────────────────────────────────────────────────────

const PLATFORMS = [
  {
    key:         'dashboard' as const,
    label:       'Dashboard',
    description: 'Your Vyom login identity',
    icon:        Globe,
    iconColor:   'text-blue-500',
    iconBg:      'bg-blue-50 dark:bg-blue-950',
    badgeColor:  'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    renderDetail: (id: DashboardIdentity) => id.username,
  },
  {
    key:         'slack' as const,
    label:       'Slack',
    description: 'Linked when you trigger tasks via /swe-agent in Slack',
    icon:        Slack,
    iconColor:   'text-purple-500',
    iconBg:      'bg-purple-50 dark:bg-purple-950',
    badgeColor:  'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    renderDetail: (id: SlackIdentity) =>
      [id.handle && `@${id.handle}`, id.user_id && `(${id.user_id})`].filter(Boolean).join(' '),
  },
  {
    key:         'github' as const,
    label:       'GitHub',
    description: 'Resolved from your email via GitHub API',
    icon:        Github,
    iconColor:   'text-gray-700 dark:text-gray-300',
    iconBg:      'bg-gray-100 dark:bg-gray-800',
    badgeColor:  'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    renderDetail: (id: GithubIdentity) => `@${id.username}`,
  },
  {
    key:         'devrev' as const,
    label:       'DevRev',
    description: 'Linked when tasks are triggered from DevRev tickets',
    icon:        Link,
    iconColor:   'text-orange-500',
    iconBg:      'bg-orange-50 dark:bg-orange-950',
    badgeColor:  'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
    renderDetail: (id: DevRevIdentity) => id.email,
  },
]

// ─── Component ────────────────────────────────────────────────────────────────

export function SettingsPage() {
  const [profile, setProfile]       = useState<UserProfile | null>(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchProfile = async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const data = await apiClient.get<UserProfile>('/api/v1/auth/me/profile')
      setProfile(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { fetchProfile() }, [])

  const linkedCount = profile ? Object.keys(profile.identities).length : 0

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-900 pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between mt-2">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
              <Settings className="w-6 h-6 mr-2 text-slate-500" />
              Settings
            </h1>
            <p className="text-muted-foreground mt-1">Your profile and connected platform identities</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchProfile(true)}
            disabled={refreshing}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2 text-red-700 dark:text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* Profile summary — full width */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5 text-slate-500" />
              Your Profile
            </CardTitle>
            <CardDescription>Identities linked across platforms you use with Vyom</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {[1, 2].map(i => (
                  <div key={i} className="h-5 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                ))}
              </div>
            ) : profile ? (
              <div className="flex items-center gap-4">
                <div className="h-14 w-14 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white text-xl font-bold shrink-0">
                  {(profile.display_name?.[0] || profile.email?.[0] || '?').toUpperCase()}
                </div>
                <div>
                  <p className="font-semibold text-slate-900 dark:text-white">{profile.display_name || '—'}</p>
                  <p className="text-sm text-muted-foreground">{profile.email}</p>
                  <Badge variant="secondary" className="mt-1 text-xs">
                    {linkedCount} platform{linkedCount !== 1 ? 's' : ''} linked
                  </Badge>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* 2×2 platform identity grid */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            Connected Identities
          </h2>
          <div className="grid grid-cols-2 gap-4">
            {PLATFORMS.map(({ key, label, description, icon: Icon, iconColor, iconBg, badgeColor, renderDetail }) => {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const identity = profile?.identities?.[key] as any
              const linked   = !!identity

              return (
                <Card key={key} className={`transition-all ${linked ? '' : 'opacity-60'}`}>
                  <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                      <div className={`h-10 w-10 rounded-lg ${iconBg} flex items-center justify-center shrink-0 mt-0.5`}>
                        <Icon className={`h-5 w-5 ${iconColor}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-sm text-slate-900 dark:text-white">{label}</span>
                          {linked
                            ? <CheckCircle className="h-3.5 w-3.5 text-green-500 shrink-0" />
                            : <span className="text-xs text-muted-foreground">not linked</span>
                          }
                        </div>
                        {loading ? (
                          <div className="h-4 w-32 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                        ) : linked ? (
                          <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-mono ${badgeColor}`}>
                            {renderDetail(identity)}
                          </span>
                        ) : (
                          <p className="text-xs text-muted-foreground leading-snug">{description}</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>

        {/* Rate limit */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            Usage
          </h2>
          <RateLimitCard />
        </div>

        {/* Footer */}
        <p className="text-xs text-muted-foreground pb-4">
          Identities are linked automatically when you trigger tasks from each platform.
          GitHub username is resolved via the GitHub API using your email.
        </p>
      </div>
    </div>
  )
}
