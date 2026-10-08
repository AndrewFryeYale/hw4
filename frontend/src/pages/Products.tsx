import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import { useChatResults } from '../chatResults'
import ProductBrowser from '../components/ProductBrowser'

export default function Products() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Results the chat assistant put on the page (see ChatWidget + chatResults.tsx).
  const { results, clearResults } = useChatResults()
  // Home page category tiles and college pennants link here as ?category=Hoodies or ?q=Saybrook.
  const [params] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category')

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch((e: Error) => setError(e.message))
  }, [])

  // A link with filters (?q= or ?category=) means the customer chose to browse the catalogue.
  if (results && !q && !category) {
    const n = results.products.length
    return (
      <section className="section">
        <div className="page-heading">
          <p className="eyebrow">From your chat</p>
          <h1>{results.title}</h1>
          <div className="chat-results-bar">
            <p className="muted">
              {n} {n === 1 ? 'match' : 'matches'} for “{results.query}”. Tap any item for sizes and details.
            </p>
            <button type="button" className="button-secondary" onClick={clearResults}>
              Show all products
            </button>
          </div>
        </div>
        {/* Keyed so filters reset when a new chat search replaces the results. */}
        <ProductBrowser key={`${results.title}|${results.query}`} products={results.products} />
      </section>
    )
  }

  return (
    <section className="section">
      <div className="page-heading">
        <h1>Shop All</h1>
        <p className="muted">
          Every piece of Bulldog gear in one place. Tap any item for sizes and details.
        </p>
      </div>
      {error && <p className="error">Couldn't load products ({error}). Is the API running?</p>}
      {!products && !error && <p className="muted">Loading products…</p>}
      {products && (
        <ProductBrowser key={params.toString()} products={products} initialText={q} initialCategory={category} />
      )}
    </section>
  )
}
