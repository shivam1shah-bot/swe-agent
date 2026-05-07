import type { StoredChatMessage } from "@/types/discover";

interface SessionCacheEntry {
  messages: StoredChatMessage[];
  timestamp: string;
}

/**
 * Session cache for handoff conversations.
 * Stores conversation state keyed by session ID for quick restoration.
 */
export function sessionCacheSet(sessionId: string, messages: StoredChatMessage[]): void {
  try {
    const key = `discover-session:${sessionId}`;
    const entry: SessionCacheEntry = {
      messages,
      timestamp: new Date().toISOString(),
    };
    sessionStorage.setItem(key, JSON.stringify(entry));
  } catch {
    // Graceful degradation
  }
}

export function sessionCacheGet(sessionId: string): SessionCacheEntry | null {
  try {
    const key = `discover-session:${sessionId}`;
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function sessionCacheRemove(sessionId: string): void {
  try {
    const key = `discover-session:${sessionId}`;
    sessionStorage.removeItem(key);
  } catch {
    // Graceful degradation
  }
}

export function sessionCacheClear(): void {
  try {
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (key?.startsWith("discover-session:")) {
        keys.push(key);
      }
    }
    keys.forEach((key) => sessionStorage.removeItem(key));
  } catch {
    // Graceful degradation
  }
}
