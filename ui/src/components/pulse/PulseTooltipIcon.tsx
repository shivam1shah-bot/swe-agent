import { HelpCircle } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

interface PulseTooltipIconProps {
  text: string
}

export function PulseTooltipIcon({ text }: PulseTooltipIconProps) {
  const [show, setShow] = useState(false)
  const [position, setPosition] = useState<'top' | 'bottom'>('top')
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (show && ref.current) {
      const rect = ref.current.getBoundingClientRect()
      setPosition(rect.top < 120 ? 'bottom' : 'top')
    }
  }, [show])

  return (
    <span
      className="relative inline-flex items-center justify-center cursor-help"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      ref={ref}
    >
      <HelpCircle size={13} className="text-blue-500 opacity-50 hover:opacity-100 transition-opacity" />
      {show && (
        <span
          className={`absolute z-50 w-56 px-3 py-2.5 text-xs font-normal leading-relaxed rounded-lg border shadow-xl pointer-events-none
            bg-card border-border text-card-foreground
            ${position === 'top' ? 'bottom-full mb-2' : 'top-full mt-2'} left-1/2 -translate-x-1/2`}
        >
          {text}
        </span>
      )}
    </span>
  )
}
