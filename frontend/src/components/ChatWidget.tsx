import { Fragment, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, matchPath, useLocation, useNavigate } from 'react-router-dom'
import {
  fetchChatHistory,
  formatPrice,
  sendChat,
  type AuthUser,
  type ChatProductCard,
  type ChatTurn,
} from '../api'
import { useAuth } from '../auth'
import { OPEN_CHAT_EVENT } from '../chatEvents'
import { useChatResults } from '../chatResults'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  products?: ChatProductCard[]
  /** Local welcome line: never sent to the agent or saved. */
  greeting?: boolean
  /** Set when this reply put search results on the Products page. */
  pageNote?: string
  error?: boolean
}

const GREETING: ChatMessage = {
  role: 'assistant',
  greeting: true,
  content:
    "Hey there! I'm the Campus Customs assistant. Ask me about sizes, colors, or finding the right Bulldog gear.",
}

function greetingFor(firstName: string | null | undefined, returning: boolean): ChatMessage {
  if (!firstName) return GREETING
  return {
    role: 'assistant',
    greeting: true,
    content: returning
      ? `Welcome back, ${firstName}! Your earlier chat is above. What can I help you find today?`
      : `Hi ${firstName}! I'm the Campus Customs assistant. Our chats are saved to your account, so you can pick up where you left off.`,
  }
}

const TEASER_KEY = 'cc.chat-teaser-seen'
function sessionGet(key: string): boolean {
  try {
    return sessionStorage.getItem(key) !== null
  } catch {
    return false
  }
}
function sessionSet(key: string) {
  try {
    sessionStorage.setItem(key, '1')
  } catch {
    // ignore: teaser may show again next page load
  }
}

/** One-tap questions that fit the page the customer is on. */
function suggestionsFor(productId: string | null, pathname: string): string[] {
  if (productId) return ['What sizes are in stock?', 'Tell me more about this', 'Show me similar items']
  if (pathname === '/products') return ['What hoodies do you have?', 'Gifts under $50', 'Anything in XXL?']
  return ['Show me crewnecks', 'Gift ideas for a Yale parent', "What's under $40?"]
}

/** Assistant text is plain, but some saved replies use **bold**; show it as bold instead of asterisks. */
function renderText(text: string) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 === 1 ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>,
  )
}

/** Earlier turns sent with each message so the agent can follow up ("the first one", "in pink?"). */
function toHistory(messages: ChatMessage[]): ChatTurn[] {
  return messages
    .filter((m) => !m.greeting && !m.error)
    .slice(-20)
    .map((m) => ({
      role: m.role,
      content: m.content,
      product_ids: m.products?.map((p) => p.product_id) ?? [],
    }))
}

// Keyed by user so logging in, switching accounts or logging out starts a fresh conversation
// (a logged-in customer's saved chat is then loaded from the server).
export default function ChatWidget() {
  const { user } = useAuth()
  return <ChatWidgetView key={user?.id ?? 'guest'} user={user} />
}

function ChatWidgetView({ user }: { user: AuthUser | null }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const { showResults } = useChatResults()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // A friendly nudge from the "shopkeeper" once per visit, after the customer has had a look around.
  const [teaser, setTeaser] = useState<string | null>(null)
  useEffect(() => {
    if (open || sessionGet(TEASER_KEY)) return
    const timer = window.setTimeout(() => {
      setTeaser(
        pathname.startsWith('/products/')
          ? 'Want to know if this comes in your size? I can check.'
          : 'Shopping for a gift or your size? I can help you find it.',
      )
    }, 8000)
    return () => window.clearTimeout(timer)
  }, [open, pathname])
  function dismissTeaser() {
    setTeaser(null)
    sessionSet(TEASER_KEY)
  }
  function openPanel() {
    setOpen(true)
    dismissTeaser()
  }

  const productId = matchPath('/products/:productId', pathname)?.params.productId ?? null

  // "Ask about this item" buttons elsewhere on the site open the chat.
  useEffect(() => {
    const openChat = () => {
      setOpen(true)
      setTeaser(null)
      sessionSet(TEASER_KEY)
    }
    window.addEventListener(OPEN_CHAT_EVENT, openChat)
    return () => window.removeEventListener(OPEN_CHAT_EVENT, openChat)
  }, [])

  // Logged in: redraw the customer's saved chat from the server. Guests start with the greeting.
  const userId = user?.id ?? null
  const firstName = user?.first_name ?? user?.name.split(' ')[0]
  useEffect(() => {
    if (userId === null) return
    let cancelled = false
    fetchChatHistory()
      .then((history) => {
        if (cancelled) return
        const saved: ChatMessage[] = history.map((m) => ({ role: m.role, content: m.content, products: m.products }))
        setMessages([...saved, greetingFor(firstName, saved.length > 0)])
      })
      .catch(() => {
        if (!cancelled) setMessages([greetingFor(firstName, false)])
      })
    return () => {
      cancelled = true
    }
  }, [userId, firstName])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, open, pending])

  function submit(e: FormEvent) {
    e.preventDefault()
    void send(draft)
  }

  async function send(raw: string) {
    const text = raw.trim()
    if (!text || pending) return
    // Guests send the conversation so far; for logged-in customers the server reads it from the DB.
    const history = user ? [] : toHistory(messages)
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setDraft('')
    setPending(true)
    try {
      const { reply, products, page_update } = await sendChat(text, history, {
        path: pathname,
        product_id: productId,
      })
      let pageNote: string | undefined
      if (page_update && page_update.products.length > 0) {
        // API contract: the agent's structured matches go straight onto the Products page.
        showResults(page_update)
        if (pathname !== '/products') navigate('/products')
        window.scrollTo({ top: 0, behavior: 'smooth' })
        const n = page_update.products.length
        pageNote = `Showing ${n} ${n === 1 ? 'item' : 'items'} on the page: ${page_update.title}`
      }
      setMessages((prev) => [...prev, { role: 'assistant', content: reply, products, pageNote }])
    } catch (err) {
      const content = err instanceof Error ? err.message : 'Something went wrong.'
      setMessages((prev) => [...prev, { role: 'assistant', content, error: true }])
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="chat-widget">
      {open && (
        <section className="chat-panel" aria-label="Campus Customs chat">
          <header className="chat-header">
            <span>Campus Customs Assistant</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close chat">
              ×
            </button>
          </header>
          <div className="chat-messages" ref={listRef} aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className="chat-turn">
                <div className={`chat-bubble ${m.role}${m.error ? ' error' : ''}`}>
                  {m.role === 'assistant' ? renderText(m.content) : m.content}
                </div>
                {m.pageNote && <div className="chat-page-note">{m.pageNote}</div>}
                {m.products && m.products.length > 0 && (
                  <div className="chat-cards">
                    {m.products.map((p) => (
                      <Link key={p.product_id} to={p.page_url} className="chat-card">
                        <img src={p.image_url} alt={p.name} loading="lazy" />
                        <div>
                          <strong>{p.name}</strong>
                          <span>{formatPrice(p.price)}</span>
                          <small>
                            {p.sizes_in_stock.length > 0
                              ? `In stock: ${p.sizes_in_stock.join(', ')}`
                              : 'Sold out'}
                          </small>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {pending && <div className="chat-bubble assistant typing">Thinking…</div>}
          </div>
          {!pending && (
            <div className="chat-suggestions" aria-label="Suggested questions">
              {suggestionsFor(productId, pathname).map((q) => (
                <button key={q} type="button" onClick={() => void send(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}
          <form className="chat-input" onSubmit={submit}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about our gear…"
              aria-label="Chat message"
              maxLength={2000}
            />
            <button type="submit" disabled={!draft.trim() || pending}>
              Send
            </button>
          </form>
        </section>
      )}
      {teaser && !open && (
        <div className="chat-teaser" role="status">
          <button type="button" className="chat-teaser-text" onClick={openPanel}>
            {teaser}
          </button>
          <button type="button" className="chat-teaser-close" onClick={dismissTeaser} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}
      <button
        type="button"
        className={`chat-toggle${open ? ' open' : ''}`}
        onClick={() => (open ? setOpen(false) : openPanel())}
        aria-label={open ? 'Close chat' : 'Open chat with the shop assistant'}
      >
        {open ? (
          '×'
        ) : (
          <>
            <span className="chat-toggle-avatar" aria-hidden="true">🐶</span>
            <span className="chat-toggle-label">Ask the shop</span>
          </>
        )}
      </button>
    </div>
  )
}
