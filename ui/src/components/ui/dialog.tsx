import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

const DialogContext = React.createContext<{ titleId: string }>({ titleId: '' })

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
  containerClassName?: string
}

const Dialog = ({ open, onOpenChange, children, containerClassName }: DialogProps) => {
  const titleId = React.useId()
  const previousFocusRef = React.useRef<HTMLElement | null>(null)
  const dialogRef = React.useRef<HTMLDivElement>(null)

  // Escape key, body overflow, focus save/restore
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false)
      }
    }

    if (open) {
      previousFocusRef.current = document.activeElement as HTMLElement
      document.addEventListener("keydown", handleEscape)
      document.body.style.overflow = "hidden"
      requestAnimationFrame(() => {
        dialogRef.current?.focus()
      })
    } else if (previousFocusRef.current) {
      previousFocusRef.current.focus()
      previousFocusRef.current = null
    }

    return () => {
      document.removeEventListener("keydown", handleEscape)
      document.body.style.overflow = "unset"
    }
  }, [open, onOpenChange])

  // Focus trap: Tab cycles within the dialog
  React.useEffect(() => {
    if (!open) return

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !dialogRef.current) return

      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      if (focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleTab)
    return () => document.removeEventListener('keydown', handleTab)
  }, [open])

  if (!open) return null

  return (
    <DialogContext.Provider value={{ titleId }}>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div
          className="fixed inset-0 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
          onClick={() => onOpenChange(false)}
        />
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          tabIndex={-1}
          className={cn(
            "relative z-50 max-h-[90vh] w-full max-w-lg mx-4 overflow-y-auto outline-none",
            containerClassName
          )}
        >
          {children}
        </div>
      </div>
    </DialogContext.Provider>
  )
}

interface DialogContentProps {
  className?: string
  children: React.ReactNode
}

const DialogContent = ({ className, children }: DialogContentProps) => (
  <div className={cn(
    "bg-background border border-border rounded-lg shadow-lg dark:shadow-2xl",
    className
  )}>
    {children}
  </div>
)

interface DialogHeaderProps {
  className?: string
  children: React.ReactNode
}

const DialogHeader = ({ className, children }: DialogHeaderProps) => (
  <div className={cn(
    "flex items-center justify-between p-6 border-b border-border",
    className
  )}>
    {children}
  </div>
)

interface DialogTitleProps {
  className?: string
  children: React.ReactNode
}

const DialogTitle = ({ className, children }: DialogTitleProps) => {
  const { titleId } = React.useContext(DialogContext)
  return (
    <h2
      id={titleId}
      className={cn(
        "text-lg font-semibold text-foreground",
        className
      )}
    >
      {children}
    </h2>
  )
}

interface DialogCloseProps {
  onClick: () => void
  className?: string
}

const DialogClose = ({ onClick, className }: DialogCloseProps) => (
  <button
    onClick={onClick}
    className={cn(
      "rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none",
      className
    )}
  >
    <X className="h-4 w-4" />
    <span className="sr-only">Close</span>
  </button>
)

interface DialogBodyProps {
  className?: string
  children: React.ReactNode
}

const DialogBody = ({ className, children }: DialogBodyProps) => (
  <div className={cn("p-6", className)}>
    {children}
  </div>
)

interface DialogFooterProps {
  className?: string
  children: React.ReactNode
}

const DialogFooter = ({ className, children }: DialogFooterProps) => (
  <div className={cn(
    "flex items-center justify-end space-x-2 p-6 border-t border-border",
    className
  )}>
    {children}
  </div>
)

export {
  Dialog,
  DialogContext,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
  DialogBody,
  DialogFooter,
}
