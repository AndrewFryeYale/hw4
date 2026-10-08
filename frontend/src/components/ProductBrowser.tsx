import { useMemo, useState } from 'react'
import type { Product } from '../api'
import { CATEGORIES, categoryOf } from '../storefront'
import ProductCard from './ProductCard'

// Filter + sort toolbar over a list of products (the full catalogue or the chat's results).

type SortKey = 'featured' | 'price-asc' | 'price-desc' | 'name'

const SORTS: Record<SortKey, { label: string; compare?: (a: Product, b: Product) => number }> = {
  featured: { label: 'Featured' },
  'price-asc': { label: 'Price: low to high', compare: (a, b) => a.price - b.price },
  'price-desc': { label: 'Price: high to low', compare: (a, b) => b.price - a.price },
  name: { label: 'Name A–Z', compare: (a, b) => a.name.localeCompare(b.name) },
}

function matchesText(p: Product, text: string): boolean {
  const haystack = [p.name, p.garment_type, p.description, ...p.colors, ...p.search_tags].join(' ').toLowerCase()
  return text
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}

interface Props {
  products: Product[]
  initialText?: string
  initialCategory?: string | null
}

export default function ProductBrowser({ products, initialText = '', initialCategory = null }: Props) {
  const [text, setText] = useState(initialText)
  const [category, setCategory] = useState<string | null>(initialCategory)
  const [sort, setSort] = useState<SortKey>('featured')
  const [inStockOnly, setInStockOnly] = useState(false)

  // Category chips list only categories present in this set of products, with counts.
  const categories = useMemo(() => {
    const counts = new Map<string, number>()
    for (const p of products) counts.set(categoryOf(p.garment_type), (counts.get(categoryOf(p.garment_type)) ?? 0) + 1)
    return [...CATEGORIES.map((c) => c.label), 'Other']
      .filter((label) => counts.has(label))
      .map((label) => ({ label, count: counts.get(label)! }))
  }, [products])

  const visible = useMemo(() => {
    const filtered = products.filter(
      (p) =>
        (!category || categoryOf(p.garment_type) === category) &&
        (!inStockOnly || p.total_stock > 0) &&
        matchesText(p, text),
    )
    const compare = SORTS[sort].compare
    return compare ? [...filtered].sort(compare) : filtered
  }, [products, category, inStockOnly, text, sort])

  const filtersOn = Boolean(text || category || inStockOnly)
  const clearFilters = () => {
    setText('')
    setCategory(null)
    setInStockOnly(false)
  }

  return (
    <>
      <div className="product-toolbar">
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Search by name, color, college, sport…"
          aria-label="Search products"
        />
        <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort products">
          {Object.entries(SORTS).map(([key, { label }]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <label className="in-stock-toggle">
          <input type="checkbox" checked={inStockOnly} onChange={(e) => setInStockOnly(e.target.checked)} />
          In stock only
        </label>
      </div>
      {categories.length > 1 && (
        <div className="category-chips" role="group" aria-label="Filter by category">
          <button type="button" className={category === null ? 'active' : ''} onClick={() => setCategory(null)}>
            All ({products.length})
          </button>
          {categories.map((c) => (
            <button
              key={c.label}
              type="button"
              className={category === c.label ? 'active' : ''}
              aria-pressed={category === c.label}
              onClick={() => setCategory(category === c.label ? null : c.label)}
            >
              {c.label} ({c.count})
            </button>
          ))}
        </div>
      )}
      <p className="muted result-count">
        Showing {visible.length} of {products.length}
        {filtersOn && (
          <>
            {' · '}
            <button type="button" className="link-button" onClick={clearFilters}>
              Clear filters
            </button>
          </>
        )}
      </p>
      {visible.length > 0 ? (
        <div className="product-grid">
          {visible.map((p) => (
            <ProductCard key={p.product_id} product={p} />
          ))}
        </div>
      ) : (
        <p className="empty-state">
          Nothing matches those filters.{' '}
          <button type="button" className="link-button" onClick={clearFilters}>
            Clear filters
          </button>{' '}
          or ask the assistant in the chat.
        </p>
      )}
    </>
  )
}
