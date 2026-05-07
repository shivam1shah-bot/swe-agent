/**
 * Tooltip component for displaying helpful information on hover.
 */

import { useState, ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface TooltipProps {
  content: string | ReactNode;
  children: ReactNode;
  className?: string;
  side?: 'top' | 'bottom' | 'left' | 'right';
  delayMs?: number;
}

export function Tooltip({ 
  content, 
  children, 
  className = '',
  side = 'top',
  delayMs = 200
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [timeoutId, setTimeoutId] = useState<NodeJS.Timeout | null>(null);

  const handleMouseEnter = () => {
    const id = setTimeout(() => {
      setIsVisible(true);
    }, delayMs);
    setTimeoutId(id);
  };

  const handleMouseLeave = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
      setTimeoutId(null);
    }
    setIsVisible(false);
  };

  const getSideClasses = () => {
    switch (side) {
      case 'top':
        return 'bottom-full left-1/2 transform -translate-x-1/2 mb-2 before:top-full before:left-1/2 before:transform before:-translate-x-1/2 before:border-t-gray-900 before:border-l-transparent before:border-r-transparent before:border-b-transparent';
      case 'bottom':
        return 'top-full left-1/2 transform -translate-x-1/2 mt-2 before:bottom-full before:left-1/2 before:transform before:-translate-x-1/2 before:border-b-gray-900 before:border-l-transparent before:border-r-transparent before:border-t-transparent';
      case 'left':
        return 'right-full top-1/2 transform -translate-y-1/2 mr-2 before:left-full before:top-1/2 before:transform before:-translate-y-1/2 before:border-l-gray-900 before:border-t-transparent before:border-b-transparent before:border-r-transparent';
      case 'right':
        return 'left-full top-1/2 transform -translate-y-1/2 ml-2 before:right-full before:top-1/2 before:transform before:-translate-y-1/2 before:border-r-gray-900 before:border-t-transparent before:border-b-transparent before:border-l-transparent';
      default:
        return 'bottom-full left-1/2 transform -translate-x-1/2 mb-2 before:top-full before:left-1/2 before:transform before:-translate-x-1/2 before:border-t-gray-900 before:border-l-transparent before:border-r-transparent before:border-b-transparent';
    }
  };

  return (
    <div 
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      
      {isVisible && (
        <div
          className={cn(
            'absolute z-50 px-3 py-2 text-sm text-white bg-gray-900 rounded-lg shadow-lg whitespace-nowrap',
            'before:content-[""] before:absolute before:w-0 before:h-0 before:border-4 before:border-solid',
            getSideClasses(),
            className
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}

// Alternative simpler version using browser's native title tooltip
export function SimpleTooltip({ 
  content, 
  children, 
  className = ''
}: { 
  content: string; 
  children: ReactNode; 
  className?: string;
}) {
  return (
    <span 
      title={content}
      className={cn('cursor-help', className)}
    >
      {children}
    </span>
  );
}
