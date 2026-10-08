import { Link } from 'react-router-dom'
import { briefDescription, formatPrice, type Product } from '../api'
import { LOW_STOCK, swatchColor } from '../storefront'

export default function ProductCard({ product }: { product: Product }) {
  const soldOut = product.total_stock === 0
  const lowStock = !soldOut && product.total_stock <= LOW_STOCK
  const swatches = product.colors
    .map((c) => ({ name: c, bg: swatchColor(c) }))
    .filter((s): s is { name: string; bg: string } => s.bg !== null)
  return (
    <Link to={`/products/${product.product_id}`} className="product-card">
      <div className="product-card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {soldOut && <span className="badge">Sold out</span>}
        {lowStock && <span className="badge badge-low">Only {product.total_stock} left</span>}
        <span className="card-peek" aria-hidden="true">
          View details →
        </span>
      </div>
      <div className="product-card-body">
        <h3>{product.name}</h3>
        <p className="product-card-desc">{briefDescription(product.description)}</p>
        <div className="product-card-foot">
          <p className="price">{formatPrice(product.price)}</p>
          {swatches.length > 0 && (
            <span className="swatches" aria-label={`Colors: ${product.colors.join(', ')}`}>
              {swatches.slice(0, 4).map((s) => (
                <span key={s.name} className="swatch" style={{ background: s.bg }} title={s.name} />
              ))}
              {swatches.length > 4 && <span className="swatch-more">+{swatches.length - 4}</span>}
            </span>
          )}
        </div>
      </div>
    </Link>
  )
}
