export interface InventoryItem {
  size: string
  quantity: number
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_file_path: string
  image_url: string
  price: number
  inventory: InventoryItem[]
  total_stock: number
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const fetchProducts = () => getJson<Product[]>('/api/products')

export const fetchProduct = (id: string) =>
  getJson<Product>(`/api/products/${encodeURIComponent(id)}`)

export const formatPrice = (price: number) => `$${price.toFixed(2)}`

/** First sentence of the catalogue description, for product cards. */
export function briefDescription(description: string, max = 90): string {
  const first = description.split(/(?<=\.)\s/)[0]
  return first.length <= max ? first : `${first.slice(0, max).trimEnd()}…`
}

export interface AuthUser {
  id: number
  first_name: string | null
  last_name: string | null
  name: string
  email: string
}

interface AuthFields {
  first_name: string
  last_name: string
  email: string
  password: string
}

async function postAuth(url: string, body: unknown): Promise<AuthUser> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : 'Something went wrong.'
    throw new Error(detail)
  }
  return data as AuthUser
}

export const registerUser = (fields: AuthFields) =>
  postAuth('/api/auth/register', fields)

export const loginUser = (email: string, password: string) =>
  postAuth('/api/auth/login', { email, password })

// ---- Chatbot (POST /api/chat → backend/agent.py) ----

export interface ChatProductCard {
  product_id: string
  name: string
  garment_type: string
  price: number
  colors: string[]
  image_url: string
  page_url: string
  sizes_in_stock: string[]
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  product_ids?: string[]
}

/** "Show these on the Products page" — products are the same `Product` shape as GET /api/products. */
export interface PageUpdate {
  title: string
  query: string
  products: Product[]
}

export interface ChatReply {
  reply: string
  products: ChatProductCard[]
  page_update: PageUpdate | null
}

/** Where the customer is on the site, so the agent knows what "this" means. */
export interface PageContext {
  path: string
  product_id: string | null
}

export async function sendChat(
  message: string,
  history: ChatTurn[],
  page?: PageContext,
): Promise<ChatReply> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, page }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : 'The assistant is unavailable right now.'
    throw new Error(detail)
  }
  return data as ChatReply
}

// ---- Session + saved chat (Problem 8). The session is an HttpOnly cookie set by log in / sign up,
// sent automatically on these same-origin requests; JS never sees the token. ----

/** The user the session cookie belongs to, or null if not logged in / session expired. */
export async function fetchMe(): Promise<AuthUser | null> {
  const res = await fetch('/api/auth/me')
  return res.ok ? ((await res.json()) as AuthUser | null) : null
}

export async function logoutUser(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' })
}

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
  products: ChatProductCard[]
  created_at: string
}

export const fetchChatHistory = () => getJson<HistoryMessage[]>('/api/chat/history')
