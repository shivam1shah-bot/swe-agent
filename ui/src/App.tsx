import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import React, { Suspense, useEffect, useState } from 'react'
import { ThemeProvider } from "@/lib/theme"
import { Header } from "@/components/layout/Header"
import { Sidebar } from "@/components/layout/Sidebar"
import { HomePage } from "@/pages/HomePage"
import { TasksPage } from "@/pages/TasksPage"
import { ExecutionLogsPage } from "@/pages/ExecutionLogsPage"
import { AutonomousAgentPage } from "@/pages/AutonomousAgentPage"
import { AiHubPage } from "@/pages/AiHubPage"
import AgentsCataloguePage from './pages/AgentsCataloguePage'
import SkillsCataloguePage from './pages/SkillsCataloguePage'
import PluginsCataloguePage from './pages/PluginsCataloguePage'
import { DynamicAgentComponent } from '@/pages/AgentsCatalogue'
import GoogleAuthCallback from './pages/AgentsCatalogue/GoogleAuthCallback'
import { MCPGatewayPage } from '@/pages/MCPGatewayPage'
import { SchedulesPage } from '@/pages/SchedulesPage'
import { TeamPage } from '@/pages/TeamPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { LoginPage } from '@/pages/Login'
import { AuthCallbackPage } from '@/pages/AuthCallback'
import { DiscoverPage } from '@/pages/DiscoverPage'
import { DiscoverSearchPage } from '@/pages/DiscoverSearchPage'
import { initializeConfig, getEnvironmentName, getApiBaseUrl } from '@/lib/environment'
import { AuthGuard } from '@/components/auth/AuthGuard'

import { Background3D } from "@/components/layout/Background3D"

// Lazy-load PulsePage — its recharts/d3 dependencies (~200KB gzipped)
// are only downloaded when a user navigates to /pulse/*
const PulsePage = React.lazy(() =>
  import('@/pages/Pulse').then(m => ({ default: m.PulsePage }))
)

function LazyFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  )
}

function App() {
  const [isConfigLoaded, setIsConfigLoaded] = useState(false)
  const [configError, setConfigError] = useState<string | null>(null)

  useEffect(() => {
    const loadConfig = async () => {
      try {
        await initializeConfig()
        console.log('✅ Configuration loaded successfully')
        console.log('🔧 Environment:', getEnvironmentName())
        console.log('🔗 API Base URL:', getApiBaseUrl())
        setIsConfigLoaded(true)
      } catch (error) {
        console.error('❌ Failed to load configuration:', error)
        setConfigError(error instanceof Error ? error.message : 'Unknown error')
        // Still allow the app to render with default config
        setIsConfigLoaded(true)
      }
    }

    loadConfig()
  }, [])

  // Show loading state while config is being loaded
  if (!isConfigLoaded) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading configuration...</p>
        </div>
      </div>
    )
  }

  // Show error state if config failed to load
  if (configError) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-500 mb-4">⚠️</div>
          <h2 className="text-xl font-semibold mb-2">Configuration Error</h2>
          <p className="text-muted-foreground mb-4">{configError}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  // Protected layout wrapper component
  const ProtectedLayout = ({ children }: { children: React.ReactNode }) => (
    <AuthGuard>
      <div className="h-screen flex flex-col bg-transparent">
        <Header />
        <div className="flex flex-1 min-h-0 bg-transparent">
          <Sidebar />
          <main className="flex-1 min-w-0 overflow-y-auto bg-transparent">
            {children}
          </main>
        </div>
      </div>
    </AuthGuard>
  );


  return (
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <Background3D />
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          
          {/* Protected Routes */}
          <Route path="/" element={<ProtectedLayout><HomePage /></ProtectedLayout>} />
          <Route path="/tasks" element={<ProtectedLayout><TasksPage /></ProtectedLayout>} />
          <Route path="/tasks/:taskId/execution-logs" element={<ProtectedLayout><ExecutionLogsPage /></ProtectedLayout>} />
          <Route path="/agents-catalogue" element={<ProtectedLayout><AgentsCataloguePage /></ProtectedLayout>} />
          <Route path="/agents-catalogue/:type/:name" element={<ProtectedLayout><DynamicAgentComponent /></ProtectedLayout>} />
          <Route path="/google-auth-callback" element={<ProtectedLayout><GoogleAuthCallback /></ProtectedLayout>} />
          <Route path="/autonomous-agent" element={<ProtectedLayout><AutonomousAgentPage /></ProtectedLayout>} />
          <Route path="/skills-catalogue" element={<ProtectedLayout><SkillsCataloguePage /></ProtectedLayout>} />
          <Route path="/schedules" element={<ProtectedLayout><SchedulesPage /></ProtectedLayout>} />
          <Route path="/plugins-catalogue" element={<ProtectedLayout><PluginsCataloguePage /></ProtectedLayout>} />
          <Route path="/mcp-gateway" element={<ProtectedLayout><MCPGatewayPage /></ProtectedLayout>} />
          <Route path="/team" element={<ProtectedLayout><TeamPage /></ProtectedLayout>} />
          <Route path="/pulse/*" element={<ProtectedLayout><Suspense fallback={<LazyFallback />}><PulsePage /></Suspense></ProtectedLayout>} />
          <Route path="/discover" element={<ProtectedLayout><DiscoverPage /></ProtectedLayout>} />
          <Route path="/discover/search" element={<ProtectedLayout><DiscoverSearchPage /></ProtectedLayout>} />
          <Route path="/ai-hub" element={<ProtectedLayout><AiHubPage /></ProtectedLayout>} />
          <Route path="/settings" element={<ProtectedLayout><SettingsPage /></ProtectedLayout>} />
        </Routes>
      </Router>
    </ThemeProvider>
  )
}

export default App
