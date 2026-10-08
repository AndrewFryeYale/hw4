import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import { openChat } from '../chatEvents'
import Pennant from '../components/Pennant'
import ProductCard from '../components/ProductCard'
import { CATEGORIES, COLLEGES, categoryOf } from '../storefront'

const FEATURED_TYPES = ['hoodie', 'crewneck', 'T-shirt', 'long-sleeve']
// Garments hung in the hero's shop window (one in-stock piece of each).
const WINDOW_TYPES = ['crewneck', 'hood', 'shirt']
// "The Family Shelf": the catalogue's Yale Mom / Dad / Grandpa… line, for gift shoppers.
const FAMILY = ['Mom', 'Dad', 'Grandma', 'Grandpa', 'Aunt', 'Uncle', 'Brother', 'Cousin']

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setProducts([]))
  }, [])

  const inStock = useMemo(() => products.filter((p) => p.total_stock > 0), [products])

  const pick = (types: string[]) =>
    types
      .map((type) => inStock.find((p) => p.garment_type.toLowerCase().includes(type.toLowerCase())))
      .filter((p): p is Product => Boolean(p))

  const featured = pick(FEATURED_TYPES)
  const windowDisplay = pick(WINDOW_TYPES)

  // One cover photo + count per shopping category.
  const categories = CATEGORIES.map(({ label }) => {
    const items = inStock.filter((p) => categoryOf(p.garment_type) === label)
    return { label, count: items.length, cover: items.find((p) => p.name.toLowerCase().includes('yale')) ?? items[0] }
  }).filter((c) => c.count > 0)

  const family = FAMILY.map((who) => ({
    who,
    item: products.find((p) => new RegExp(`\\b${who}\\b`, 'i').test(p.name)),
  })).filter((f) => f.item)

  return (
    <>
      {/* Storefront: awning, shop window with real garments on a rail, open sign. */}
      <section className="storefront" aria-label="Welcome to Campus Customs">
        <div className="awning" aria-hidden="true" />
        <div className="storefront-body">
          <div className="storefront-copy">
            <span className="open-sign">
              <span className="open-dot" /> Come on in, we're open
            </span>
            <p className="eyebrow">Officially licensed Yale gear · 57 Broadway</p>
            <h1>
              Bulldog Blue, <em>head to toe.</em>
            </h1>
            <p className="lede">
              Cozy hoodies, everyday tees, and game-day classics, picked for chilly walks across Old
              Campus, Saturdays in the Bowl, and every visit home in between.
            </p>
            <div className="cta-row">
              <Link to="/products" className="button">
                Shop the collection
              </Link>
              <button type="button" className="button-ghost" onClick={openChat}>
                Ask the shop assistant
              </button>
            </div>
          </div>
          <div className="shop-window" aria-label="In the window this week">
            <div className="window-rail" aria-hidden="true" />
            <div className="window-items">
              {windowDisplay.map((p, i) => (
                <Link key={p.product_id} to={`/products/${p.product_id}`} className={`hanger hanger-${i}`}>
                  <span className="hanger-hook" aria-hidden="true" />
                  <img src={p.image_url} alt={p.name} />
                  <span className="price-tag">${p.price.toFixed(0)}</span>
                </Link>
              ))}
            </div>
            <span className="window-label">In the window this week</span>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <h2>Shop by category</h2>
          <Link to="/products">Browse everything →</Link>
        </div>
        <div className="category-tiles">
          {categories.map((c) => (
            <Link key={c.label} to={`/products?category=${encodeURIComponent(c.label)}`} className="category-tile">
              {c.cover && <img src={c.cover.image_url} alt="" loading="lazy" />}
              <span className="category-tile-label">
                {c.label}
                <small>{c.count} in stock</small>
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="section college-wall">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Find your college</p>
            <h2>Hang your colors</h2>
          </div>
          <p className="muted">Crests and colors for 11 residential colleges. Pick yours.</p>
        </div>
        <div className="pennants">
          {COLLEGES.map((c, i) => (
            <Link
              key={c.name}
              to={`/products?q=${encodeURIComponent(c.name)}`}
              className="pennant-link"
              style={{ ['--tilt' as string]: `${i % 2 ? 3 : -3}deg` }}
              title={`${c.name} College gear`}
            >
              <Pennant label={c.short} color={c.color} trim={c.trim} />
            </Link>
          ))}
        </div>
      </section>

      {family.length > 0 && (
        <section className="section family-shelf">
          <div className="family-card">
            <div>
              <p className="eyebrow">The family shelf</p>
              <h2>Visiting family? Send them home in blue.</h2>
              <p className="muted">
                Yale Mom, Dad, Grandpa and more: the gifts parents and grandparents actually wear.
              </p>
            </div>
            <div className="family-tags">
              {family.map(({ who }) => (
                <Link key={who} to={`/products?q=${encodeURIComponent(`Yale ${who}`)}`} className="gift-tag">
                  Yale {who}
                </Link>
              ))}
              <button type="button" className="gift-tag gift-tag-help" onClick={openChat}>
                Not sure? Ask for gift ideas
              </button>
            </div>
          </div>
        </section>
      )}

      <section className="section">
        <div className="section-heading">
          <h2>Fan favorites</h2>
          <Link to="/products">View all →</Link>
        </div>
        {featured.length > 0 ? (
          <div className="product-grid">
            {featured.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
        ) : (
          <p className="muted">Fresh picks loading…</p>
        )}
      </section>

      <section className="section promo-row">
        <div className="promo">
          <span className="promo-icon" aria-hidden="true">🧣</span>
          <h3>Layer Up, Bulldogs</h3>
          <p>Soft crewnecks and hoodies built for chilly walks across Old Campus.</p>
        </div>
        <div className="promo">
          <span className="promo-icon" aria-hidden="true">🏒</span>
          <h3>Rep Your Team</h3>
          <p>From crew to hockey to fencing, find left-chest gear for the sport you love.</p>
        </div>
        <div className="promo">
          <span className="promo-icon" aria-hidden="true">🏈</span>
          <h3>Game Day Ready</h3>
          <p>Rivalry tees and bold Big Yale looks for The Game and every Saturday after.</p>
        </div>
      </section>

      <section className="section visit-card">
        <div>
          <p className="eyebrow">Stop by the shop</p>
          <h2>57 Broadway, New Haven</h2>
          <p className="muted">Steps from campus. Find your size, pick up a gift, and say hi.</p>
        </div>
        <a
          className="button"
          href="https://www.google.com/maps/search/?api=1&query=57+Broadway+New+Haven+CT+06511"
          target="_blank"
          rel="noreferrer"
        >
          Get directions
        </a>
      </section>
    </>
  )
}
