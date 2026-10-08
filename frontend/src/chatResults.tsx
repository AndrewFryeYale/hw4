import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import type { PageUpdate } from './api'

// Chat search results shown on the Products page. Kept in context (and sessionStorage) so they survive
// opening a product and coming back with "Back to all products" or the browser back button.

const STORAGE_KEY = 'campus-customs-chat-results'

interface ChatResultsValue {
  results: PageUpdate | null
  showResults: (update: PageUpdate) => void
  clearResults: () => void
}

const ChatResultsContext = createContext<ChatResultsValue | null>(null)

function loadStored(): PageUpdate | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as PageUpdate) : null
  } catch {
    return null
  }
}

function store(update: PageUpdate | null) {
  try {
    if (update) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(update))
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage unavailable (private mode etc.): results still live in memory for this visit.
  }
}

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<PageUpdate | null>(loadStored)

  const showResults = useCallback((update: PageUpdate) => {
    setResults(update)
    store(update)
  }, [])

  const clearResults = useCallback(() => {
    setResults(null)
    store(null)
  }, [])

  return (
    <ChatResultsContext.Provider value={{ results, showResults, clearResults }}>
      {children}
    </ChatResultsContext.Provider>
  )
}

export function useChatResults(): ChatResultsValue {
  const ctx = useContext(ChatResultsContext)
  if (!ctx) throw new Error('useChatResults must be used inside ChatResultsProvider')
  return ctx
}
