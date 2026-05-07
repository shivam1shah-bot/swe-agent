import type { ChatHistoryEntry, StoredChatMessage } from "@/types/discover";
import type { ChatMessage } from "@/types/discover";

const STORAGE_KEY = "discover-chat-history";
const MAX_ENTRIES = 50;
const DEFAULT_TITLE_MAX_LEN = 60;

/** Derive a short default title from the first user message in the conversation */
export function defaultTitleFromMessages(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser || typeof firstUser.content !== "string") return "";
  const text = firstUser.content.trim();
  if (!text) return "";
  if (text.length <= DEFAULT_TITLE_MAX_LEN) return text;
  return text.slice(0, DEFAULT_TITLE_MAX_LEN).trim() + "…";
}

export function getChatHistory(): ChatHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function saveHistory(history: ChatHistoryEntry[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
}

/** Convert ChatMessage[] to serializable StoredChatMessage[] */
export function toStored(messages: ChatMessage[]): StoredChatMessage[] {
  return messages
    .filter((m) => {
      if (m.isLoading) return false;        // still in initial loading dots
      if (m.isThinking) return false;       // thinking but no content yet
      // drop empty assistant bubbles — these are mid-stream or error states
      // with nothing useful to persist
      if (m.role === "assistant" && !m.content.trim()) return false;
      return true;
    })
    .map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      code_refs: m.code_refs,
      doc_links: m.doc_links,
      timestamp:
        m.timestamp instanceof Date
          ? m.timestamp.toISOString()
          : (m.timestamp as unknown as string),
    }));
}

/** Convert StoredChatMessage[] back to ChatMessage[] */
export function fromStored(stored: StoredChatMessage[]): ChatMessage[] {
  return stored.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    code_refs: m.code_refs,
    doc_links: m.doc_links,
    timestamp: new Date(m.timestamp),
  }));
}

/** Update an existing chat entry with new messages, optional session_id, and optional title */
export function updateChatEntry(
  id: string,
  messages: ChatMessage[],
  sessionId?: string,
  title?: string
): void {
  try {
    const history = getChatHistory();
    const index = history.findIndex((e) => e.id === id);
    if (index === -1) return;

    history[index].messages = toStored(messages);
    if (sessionId) history[index].session_id = sessionId;
    if (title !== undefined) history[index].title = title;
    history[index].timestamp = new Date().toISOString();

    // Move to top of list
    const [entry] = history.splice(index, 1);
    history.unshift(entry);

    saveHistory(history);
  } catch {
    // Graceful degradation
  }
}

/** Get a single chat entry by id */
export function getChatEntry(id: string): ChatHistoryEntry | undefined {
  return getChatHistory().find((e) => e.id === id);
}

/**
 * Patch save/share metadata on an existing entry without touching messages.
 * No-op if the entry does not exist.
 */
export function updateChatEntryMeta(
  id: string,
  meta: {
    saved_expires_at?: string;
    share_url?: string;
    share_expires_at?: string;
  }
): void {
  try {
    const history = getChatHistory();
    const index = history.findIndex((e) => e.id === id);
    if (index === -1) return;
    if (meta.saved_expires_at !== undefined) history[index].saved_expires_at = meta.saved_expires_at;
    if (meta.share_url !== undefined) history[index].share_url = meta.share_url;
    if (meta.share_expires_at !== undefined) history[index].share_expires_at = meta.share_expires_at;
    saveHistory(history);
  } catch {
    // Graceful degradation
  }
}

/**
 * Create a new chat entry with messages already stored.
 * Used when explicitly saving an in-memory (ephemeral) conversation for the first time.
 * Returns the new entry id.
 */
export function saveChatEntryFull(
  query: string,
  messages: ChatMessage[],
  sessionId?: string,
  title?: string
): string {
  try {
    const trimmed = query.trim();
    if (!trimmed) return "";
    const history = getChatHistory();
    const newEntry: ChatHistoryEntry = {
      id: crypto.randomUUID(),
      query: trimmed,
      title: title || defaultTitleFromMessages(messages) || trimmed.slice(0, DEFAULT_TITLE_MAX_LEN),
      timestamp: new Date().toISOString(),
      messages: toStored(messages),
      session_id: sessionId,
    };
    const updated = [newEntry, ...history].slice(0, MAX_ENTRIES);
    saveHistory(updated);
    return newEntry.id;
  } catch {
    return "";
  }
}

export function deleteChatEntry(id: string): void {
  try {
    const history = getChatHistory();
    const updated = history.filter((entry) => entry.id !== id);
    saveHistory(updated);
  } catch {
    // Graceful degradation
  }
}

export function clearChatHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Graceful degradation
  }
}
