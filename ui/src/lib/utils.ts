import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format Unix timestamp (in seconds or milliseconds) to a readable date string
 * @param timestamp - Unix timestamp in seconds or milliseconds
 * @param includeTime - Whether to include time in the output
 * @returns Formatted date string or 'Invalid date' if timestamp is invalid
 */
export function formatTimestamp(timestamp: number | string, includeTime: boolean = false): string {
  try {
    let date: Date;
    
    // Handle string timestamps (ISO format)
    if (typeof timestamp === 'string') {
      date = new Date(timestamp);
    } else {
      // Handle numeric timestamps - detect if seconds or milliseconds
      // If timestamp is less than a reasonable year 2000 timestamp in milliseconds,
      // assume it's in seconds and convert to milliseconds
      const timestampMs = timestamp < 946684800000 ? timestamp * 1000 : timestamp;
      date = new Date(timestampMs);
    }
    
    if (isNaN(date.getTime())) {
      return 'Invalid date';
    }
    
    if (includeTime) {
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } else {
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    }
  } catch (_error) {
    return 'Invalid date';
  }
}

/**
 * Format Unix timestamp to a relative time string (e.g., "2 hours ago")
 * @param timestamp - Unix timestamp in seconds or milliseconds
 * @returns Relative time string or 'Invalid date' if timestamp is invalid
 */
export function formatRelativeTime(timestamp: number | string): string {
  try {
    let date: Date;
    
    if (typeof timestamp === 'string') {
      date = new Date(timestamp);
    } else {
      const timestampMs = timestamp < 946684800000 ? timestamp * 1000 : timestamp;
      date = new Date(timestampMs);
    }
    
    if (isNaN(date.getTime())) {
      return 'Invalid date';
    }
    
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffSecs < 60) {
      return 'Just now';
    } else if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return formatTimestamp(timestamp, false);
    }
  } catch (_error) {
    return 'Invalid date';
  }
} 