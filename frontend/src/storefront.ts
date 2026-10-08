// Shared storefront data: shopping categories, residential colleges, color swatches, stock signals.

export const CATEGORIES = [
  { label: 'Hoodies', test: (t: string) => t.includes('hood') },
  { label: 'Quarter-zips', test: (t: string) => t.includes('quarter-zip') || t.includes('1/4') },
  { label: 'Jackets & fleece', test: (t: string) => t.includes('jacket') || t.includes('fleece') },
  { label: 'Crewnecks', test: (t: string) => t.includes('crew') || t.includes('sweatshirt') },
  { label: 'Tees & shirts', test: (t: string) => t.includes('shirt') },
] as const

/** First matching category for a garment type, checked in the order above (a hooded sweatshirt is a Hoodie). */
export function categoryOf(garmentType: string): string {
  const t = garmentType.toLowerCase()
  return CATEGORIES.find((c) => c.test(t))?.label ?? 'Other'
}

/** Residential colleges with gear in the catalogue, each with its pennant colors. */
export const COLLEGES = [
  { name: 'Benjamin Franklin', short: 'Franklin', color: '#1d3f6e', trim: '#c19a49' },
  { name: 'Berkeley', short: 'Berkeley', color: '#8a1c2b', trim: '#f3e6c4' },
  { name: 'Branford', short: 'Branford', color: '#7a1f1f', trim: '#f2f2f2' },
  { name: 'Davenport', short: 'Davenport', color: '#a52a2a', trim: '#f3e6c4' },
  { name: 'Grace Hopper', short: 'Hopper', color: '#2b4c7e', trim: '#f3e6c4' },
  { name: 'Jonathan Edwards', short: 'JE', color: '#5b1f2a', trim: '#c19a49' },
  { name: 'Morse', short: 'Morse', color: '#9e1b32', trim: '#f2f2f2' },
  { name: 'Pierson', short: 'Pierson', color: '#3c2a5e', trim: '#f3e6c4' },
  { name: 'Saybrook', short: 'Saybrook', color: '#2f5233', trim: '#f2f2f2' },
  { name: 'Timothy Dwight', short: 'TD', color: '#2a6b3a', trim: '#f3e6c4' },
  { name: 'Trumbull', short: 'Trumbull', color: '#1f3b57', trim: '#c19a49' },
] as const

const SWATCHES: [string, string][] = [
  ['multicolor', 'conic-gradient(#00356b, #a5432f, #c19a49, #2e6b3f, #00356b)'],
  ['charcoal', '#4a4d52'],
  ['heather gray', '#b8bbbf'],
  ['light gray', '#d4d6d9'],
  ['gray', '#9a9ea3'],
  ['light blue', '#9cc3e6'],
  ['royal blue', '#2a4fb5'],
  ['navy', '#1f2a44'],
  ['blue', '#2b5ea8'],
  ['coral', '#e98a74'],
  ['red', '#b3282d'],
  ['black', '#16181b'],
  ['white', '#ffffff'],
  ['cream', '#f3ead3'],
  ['ivory', '#f6f0df'],
  ['yellow', '#f2c230'],
  ['gold', '#c19a49'],
  ['green', '#2e6b3f'],
]

/** CSS background for a catalogue color name ("navy blue", "heather gray"…), or null if unknown/blank. */
export function swatchColor(name: string): string | null {
  const n = name.toLowerCase()
  return SWATCHES.find(([key]) => n.includes(key))?.[1] ?? null
}

/** Honest scarcity signal: only shown when stock is genuinely low. */
export const LOW_STOCK = 15
export const LOW_SIZE_STOCK = 3
