import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { createContext } from 'react'
import { BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { usePulseRepos } from '@/hooks/usePulseData'
import { PulseOverviewPage } from './PulseOverviewPage'
import { PulseRepositoriesPage } from './PulseRepositoriesPage'
import { PulseCommitsPage } from './PulseCommitsPage'
import { PulsePromptsPage } from './PulsePromptsPage'
import { PulseLeaderboardPage } from './PulseLeaderboardPage'
import { PulseErrorBoundary } from './PulseErrorBoundary'

export const PulseReposContext = createContext<string[]>([])

const subPages = [
  { path: 'overview', label: 'Overview' },
  { path: 'repositories', label: 'Repositories' },
  { path: 'commits', label: 'Commits' },
  { path: 'prompts', label: 'Prompts' },
  { path: 'leaderboard', label: 'Leaderboard' },
]

export function PulsePage() {
  const { data: repoData } = usePulseRepos({ days: 30 })
  const repos = repoData?.repos?.map(r => r.repo) || []

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="relative z-10 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center">
              <BarChart3 className="w-6 h-6 mr-2 text-blue-500" />
              Pulse
            </h1>
            <p className="text-muted-foreground mt-1">
              Track AI usage, costs, and developer productivity
            </p>
          </div>
        </div>

        {/* Sub-navigation tabs */}
        <nav className="flex space-x-1 bg-muted/50 rounded-lg p-1 w-fit">
          {subPages.map((page) => (
            <NavLink
              key={page.path}
              to={`/pulse/${page.path}`}
              className={({ isActive }) =>
                cn(
                  'px-4 py-2 rounded-md text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )
              }
            >
              {page.label}
            </NavLink>
          ))}
        </nav>

        {/* Page content */}
        <PulseErrorBoundary>
        <PulseReposContext.Provider value={repos}>
        <Routes>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<PulseOverviewPage />} />
          <Route path="repositories" element={<PulseRepositoriesPage />} />
          <Route path="commits" element={<PulseCommitsPage />} />
          <Route path="prompts" element={<PulsePromptsPage />} />
          <Route path="leaderboard" element={<PulseLeaderboardPage />} />
        </Routes>
        </PulseReposContext.Provider>
        </PulseErrorBoundary>
      </div>
    </div>
  )
}
