import { Settings, User, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../ui/button'
import { ThemeToggle } from '../ui/theme-toggle'
import { Badge } from '../ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
import { getEnvironmentName } from '@/lib/environment'

// Get user info from JWT token
function getUserInfo(): { email: string | null; firstName: string | null } {
  const token = localStorage.getItem('auth_token')
  if (!token) return { email: null, firstName: null }
  
  try {
    // Decode JWT payload (base64)
    const payload = token.split('.')[1]
    const decoded = JSON.parse(atob(payload))
    const email = decoded.sub || decoded.email || null
    
    // Extract first name from email (e.g., "nehal.kumarsingh@razorpay.com" -> "Nehal")
    let firstName: string | null = null
    if (email) {
      const localPart = email.split('@')[0] // "nehal.kumarsingh"
      const firstPart = localPart.split('.')[0] // "nehal"
      firstName = firstPart.charAt(0).toUpperCase() + firstPart.slice(1).toLowerCase()
    }
    
    return { email, firstName }
  } catch {
    return { email: null, firstName: null }
  }
}

export function Header() {
  const navigate = useNavigate()
  
  const { firstName, email } = getUserInfo()
  
  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('basic_auth_creds')
    navigate('/login')
  }
  // Get environment-specific styling and icon
  const getEnvironmentBadge = () => {
    const env = getEnvironmentName();

    switch (env) {
      case 'dev':
      case 'dev_docker':
        return {
          icon: '🔧',
          className: 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700'
        };
      case 'stage':
        return {
          icon: '🚀',
          className: 'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-700'
        };
      case 'prod':
        return {
          icon: '🌟',
          className: 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border-green-200 dark:border-green-700'
        };
      default:
        return {
          icon: '⚙️',
          className: 'bg-gray-50 dark:bg-gray-900/20 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700'
        };
    }
  };

  // Format environment name for display
  const formatEnvironmentName = (env: string): string => {
    switch (env) {
      case 'dev_docker':
        return 'Dev Docker';
      case 'dev':
        return 'Dev';
      case 'stage':
        return 'Stage';
      case 'prod':
        return 'Prod';
      default:
        return env.charAt(0).toUpperCase() + env.slice(1);
    }
  };

  const { icon, className } = getEnvironmentBadge();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/60 backdrop-blur-md supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between px-6">
        {/* Logo */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1">
            <div className="h-10 w-auto rounded-lg flex items-center justify-center">
              <img
                src="/rzp-logo.svg"
                alt="Vyom"
                className="h-6 w-auto object-contain drop-shadow-sm"
              />
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight">
              <span className="text-slate-900 dark:text-white mr-1.5">Razorpay</span>
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500">Vyom</span>
            </h1>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-3">
          {/* Environment Display for all environments */}
          <Badge variant="outline" className={`${className} px-3 py-1 font-medium shadow-sm`}>
            <span className="mr-1.5">{icon}</span> {formatEnvironmentName(getEnvironmentName())}
          </Badge>
          
          <div className="h-6 w-px bg-border/50 mx-2" />
          
          <ThemeToggle />
          
          {/* User Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="relative h-9 w-9 rounded-full ml-1 border border-border/50 bg-muted/30 hover:bg-muted/60 transition-colors">
                <span className="text-sm font-semibold text-foreground">
                  {firstName ? firstName.charAt(0) : <User className="h-4 w-4" />}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 mt-1 rounded-xl p-2 bg-background/95 backdrop-blur-xl border-border/50 shadow-xl">
              <DropdownMenuLabel className="font-normal px-2 py-2">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none text-foreground">
                    {firstName ? `Hi ${firstName}` : 'Account'}
                  </p>
                  {email && (
                    <p className="text-xs leading-none text-muted-foreground mt-1 truncate max-w-[200px]">
                      {email}
                    </p>
                  )}
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-border/50 my-1" />
              <DropdownMenuItem onClick={() => navigate('/settings')} className="rounded-lg cursor-pointer px-2 py-2 text-muted-foreground hover:text-foreground focus:text-foreground">
                <Settings className="mr-2 h-4 w-4" />
                <span>Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleLogout} destructive className="rounded-lg cursor-pointer px-2 py-2 mt-1 text-red-600 dark:text-red-400 focus:text-red-600 focus:bg-red-50 dark:focus:bg-red-950/50">
                <LogOut className="mr-2 h-4 w-4" />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}