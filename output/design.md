# Design — "The Shop on Broadway"

**Concept:** the site should feel like walking up to a real campus store on Broadway: a striped awning,
a shop window, felt pennants, brass fittings, and a shopkeeper who says hi. Every element either **pulls
a visitor in** (attract) or **moves them one step closer to a product page** (convert). All claims and
numbers come from the real catalogue and stock. Nothing is invented (no fake sales, reviews or policies).

| # | Change | What it is | How it helps the store |
|---|---|---|---|
| 1 | **Warm brand system** | Cream "paper" background, Yale blue signage, brass accents, brick for urgency. *Fraunces* serif headings + *Inter* body. "CC" crest + "57 Broadway · New Haven" lockup. | Feels like a cozy local shop, not a template. Trust and warmth keep people browsing. The address in the logo says "real store, near you". |
| 2 | **Storefront hero** | Scalloped awning; a pulsing "Come on in, we're open" sign; a **shop window** with 3 in-stock garments on hangers, each with a price tag (live data); two CTAs: *Shop the collection* / *Ask the shop assistant*. | The first screen shows real products and prices, not just a slogan. Every garment in the window is clickable, so the hero itself sells. |
| 3 | **Announcement ticker** | Scrolling strip of true facts (licensed, 11 colleges, live stock, address) + a fixed *"Need a size? Ask us →"* button. Pauses on hover; static for reduced-motion users. | Answers "can I trust this / do you have my size?" before it's asked, and keeps a path to help visible on every page. |
| 4 | **Shop by category tiles** | 5 photo tiles (Hoodies 27, Crewnecks 30…) with live in-stock counts, linking to the pre-filtered Products page. | Shortens the path from homepage to the right rack to one click. The counts show there's plenty to choose from. |
| 5 | **"Hang your colors" pennant wall** | 11 SVG felt pennants in college colors, one per residential college with gear, each linking to that college's products. | Yale-specific and personal. Students shop for *their* college, and identity is the strongest reason to buy campus gear. |
| 6 | **The Family Shelf** | Gift-tag links (Yale Mom, Dad, Grandma, Grandpa, Aunt, Uncle, Brother, Cousin) + *"Not sure? Ask for gift ideas"*. | Targets visiting parents and gift buyers, a high-intent audience, with a one-click path to the family line. |
| 7 | **Product cards that sell** | Color swatches, an honest **"Only N left"** badge (real stock ≤ 15: 3 products), image zoom and a *View details →* slide-up on hover. | Swatches answer "what colors?" at a glance. Genuine scarcity nudges hesitant buyers. Hover cues invite the click. |
| 8 | **Product page that closes the sale** | Swatch chips; sizes with ≤ 3 left get a brick underline plus *"Only 2 left in S. Grab it while it's here."*; assurances (licensed, live stock, visit us); **Complete the look**: 4 in-stock pieces from other categories, matching colors first. | Removes last-second doubts at the moment of decision, and cross-sells into a bigger basket. |
| 9 | **Friendly shopkeeper chat** | Launcher becomes *"🐶 Ask the shop"* with a brass ring. After 8 s, a one-time teaser: *"Want to know if this comes in your size? I can check."* (product pages) / *"Shopping for a gift or your size?"*. Dismissed for good once opened or closed. | Like a clerk saying hello: it rescues undecided visitors and routes them to the AI that finds and links products. It shows only once, so it never nags. |
| 10 | **Storefront footer + visit card** | Dark footer with brass trim, address, **Get directions** (Google Maps), quick shop links; a dashed "Stop by the shop" card on Home. | Converts online browsers into foot traffic, and gives one more route back into the catalogue. |

**Polish & checks:**
- Fully responsive. Tested at 390 px wide with no horizontal scroll; on phones the launcher shrinks to the avatar.
- Respects `prefers-reduced-motion`.
- No console errors. Guest `/api/auth/me` now returns `null` instead of a 401.
- All earlier flows still work in headless Chrome:
  - category tile → Hoodies (27)
  - Saybrook pennant → 3 products
  - Yale Dad tag → the 3 Dad items
  - product page → "Complete the look" + low-size note
  - teaser shows once and is dismissed after opening

**Files:** `index.html` (fonts), `src/index.css` (design tokens + storefront styles), `src/storefront.ts`
(categories, colleges, swatches, stock thresholds), `components/AnnouncementBar.tsx`, `components/Pennant.tsx`,
`pages/Home.tsx`, `components/ProductCard.tsx`, `pages/ProductDetail.tsx`, `components/ChatWidget.tsx`,
`components/NavBar.tsx`, `App.tsx` (footer), `pages/Products.tsx` (`?category=` / `?q=` links).
