import {
  Home,
  Store,
  Bot,
  Zap,
  Activity,
  Users,
  Sparkles,
  Clock,
  Puzzle,
  BarChart3,
  Telescope,
  LayoutGrid,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface NavItem {
  title: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
  description?: string
}

const navItems: NavItem[] = [
  {
    title: 'Home',
    href: '/',
    icon: Home,
  },
  {
    title: 'Discover',
    href: '/discover',
    icon: Telescope,
  },
  {
    title: 'AI Hub',
    href: '/ai-hub',
    icon: LayoutGrid,
    badge: 'New',
  },
  {
    title: 'Autonomous Agent',
    href: '/autonomous-agent',
    icon: Bot,
  },
  {
    title: 'Agents Catalogue',
    href: '/agents-catalogue',
    icon: Store,
  },
  {
    title: 'Skills Catalogue',
    href: '/skills-catalogue',
    icon: Sparkles,
  },
  {
    title: 'Plugins Catalogue',
    href: '/plugins-catalogue',
    icon: Puzzle,
  },
  {
    title: 'Tasks',
    href: '/tasks',
    icon: Activity,
  },
  {
    title: 'Schedules',
    href: '/schedules',
    icon: Clock,
  },
  {
    title: 'MCP Gateway',
    href: '/mcp-gateway',
    icon: Zap,
  },
  {
    title: 'Team',
    href: '/team',
    icon: Users,
  },
  {
    title: 'Pulse',
    href: '/pulse',
    icon: BarChart3,
  },
]

export function Sidebar() {

  return (
    <div className="w-64 border-r bg-background/40 backdrop-blur-md min-h-[calc(100vh-4rem)]">
      <nav className="p-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            className={({ isActive }) =>
              cn(
                "flex items-center space-x-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                (isActive)
                  ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800"
              )
            }
          >
            <item.icon className="h-4 w-4" />
            <span className="flex-1">{item.title}</span>
            {item.badge && (
              <span className="px-2 py-0.5 text-xs bg-primary text-primary-foreground rounded-full">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}