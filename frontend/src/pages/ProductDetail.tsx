import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchProduct, fetchProducts, formatPrice, type Product } from '../api'
import ProductCard from '../components/ProductCard'
import { LOW_SIZE_STOCK, categoryOf, swatchColor } from '../storefront'
import { openChat } from '../chatEvents'

// Keyed by id so state resets cleanly when navigating between products.
export default function ProductDetail() {
  const { productId = '' } = useParams()
  return <ProductDetailView key={productId} productId={productId} />
}

function ProductDetailView({ productId }: { productId: string }) {
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [size, setSize] = useState<string | null>(null)
  const [related, setRelated] = useState<Product[]>([])

  useEffect(() => {
    fetchProduct(productId)
      .then(setProduct)
      .catch((e: Error) => setError(e.message))
  }, [productId])

  // "Complete the look": in-stock pieces from a different category, favouring the same colors.
  useEffect(() => {
    if (!product) return
    const category = categoryOf(product.garment_type)
    fetchProducts()
      .then((all) => {
        const sharesColor = (p: Product) => p.colors.some((c) => product.colors.includes(c))
        const picks = all
          .filter((p) => p.product_id !== product.product_id && p.total_stock > 0 && categoryOf(p.garment_type) !== category)
          .sort((a, b) => Number(sharesColor(b)) - Number(sharesColor(a)))
        // One per category so the row reads like an outfit, not four of the same thing.
        const seen = new Set<string>()
        setRelated(picks.filter((p) => !seen.has(categoryOf(p.garment_type)) && seen.add(categoryOf(p.garment_type))).slice(0, 4))
      })
      .catch(() => setRelated([]))
  }, [product])

  if (error) {
    return (
      <section className="section">
        <p className="error">We couldn't find that item.</p>
        <Link to="/products">← Back to all products</Link>
      </section>
    )
  }
  if (!product) return <section className="section muted">Loading…</section>

  const selected = product.inventory.find((i) => i.size === size)

  return (
    <section className="section">
      <Link to="/products" className="back-link">
        ← Back to all products
      </Link>
      <div className="product-detail">
        <div className="product-detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>
        <div className="product-detail-info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="price large">{formatPrice(product.price)}</p>
          <p>{product.description}</p>

          <h3>Colors</h3>
          <ul className="chips">
            {product.colors.filter(Boolean).map((c) => (
              <li key={c}>
                {swatchColor(c) && <span className="swatch" style={{ background: swatchColor(c)! }} />}
                {c}
              </li>
            ))}
          </ul>

          <h3>Size</h3>
          <div className="sizes">
            {product.inventory.map((item) => (
              <button
                key={item.size}
                type="button"
                className={`size${size === item.size ? ' selected' : ''}${
                  item.quantity > 0 && item.quantity <= LOW_SIZE_STOCK ? ' low' : ''
                }`}
                title={item.quantity === 0 ? 'Sold out' : `${item.quantity} in stock`}
                disabled={item.quantity === 0}
                onClick={() => setSize(item.size)}
              >
                {item.size}
              </button>
            ))}
          </div>
          <p className="muted stock-note">
            {product.total_stock === 0
              ? 'Sold out in every size.'
              : selected
                ? selected.quantity <= LOW_SIZE_STOCK
                  ? `Only ${selected.quantity} left in ${selected.size}. Grab it while it's here.`
                  : `${selected.quantity} left in ${selected.size}.`
                : 'Pick a size to check availability.'}
          </p>
          <button
            type="button"
            className="button-secondary ask-assistant"
            onClick={openChat}
          >
            Ask our assistant about this item
          </button>
          <ul className="assurances">
            <li>✔ Officially licensed Yale apparel</li>
            <li>✔ Live stock: what you see is on our shelves</li>
            <li>✔ Or visit us at 57 Broadway, New Haven</li>
          </ul>
        </div>
      </div>
      {related.length > 0 && (
        <div className="related">
          <h2>Complete the look</h2>
          <div className="product-grid">
            {related.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
