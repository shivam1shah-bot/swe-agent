/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { useState } from 'react'
import { Moon, Sun, Monitor, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/lib/theme'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [isOpen, setIsOpen] = useState(false)

  const themes = [
    { key: 'light', label: 'Light', icon: Sun },
    { key: 'dark', label: 'Dark', icon: Moon },
    { key: 'system', label: 'System', icon: Monitor },
  ]

  const currentTheme = themes.find(t => t.key === theme)
  const CurrentIcon = currentTheme?.icon || Monitor

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        className="h-8 px-2"
        onClick={() => setIsOpen(!isOpen)}
      >
        <CurrentIcon className="h-4 w-4 mr-1" />
        <span className="hidden sm:inline">{currentTheme?.label}</span>
        <ChevronDown className="h-3 w-3 ml-1 opacity-60" />
      </Button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-1 z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
            {themes.map((themeOption) => {
              const Icon = themeOption.icon
              return (
                <div
                  key={themeOption.key}
                  onClick={() => {
                    setTheme(themeOption.key as any)
                    setIsOpen(false)
                  }}
                  className={`relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground ${
                    theme === themeOption.key ? 'bg-accent' : ''
                  }`}
                >
                  <Icon className="h-4 w-4 mr-2" />
                  {themeOption.label}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

// Simple version for mobile or when you want just a toggle
export function SimpleThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
      className="relative"
    >
      <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}