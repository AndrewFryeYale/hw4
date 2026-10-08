// A felt college pennant drawn in SVG, used for the "Find your college" wall and the brand mark.
export default function Pennant({ label, color, trim, width = 120 }: { label: string; color: string; trim: string; width?: number }) {
  return (
    <svg viewBox="0 0 120 48" width={width} height={(width * 48) / 120} role="img" aria-label={`${label} pennant`}>
      <rect x="0" y="0" width="10" height="48" rx="2" fill={trim} />
      <path d="M10 2 L118 24 L10 46 Z" fill={color} />
      <path d="M10 2 L118 24 L10 46" fill="none" stroke={trim} strokeWidth="1.5" strokeDasharray="3 3" />
      <text x="20" y="28.5" fontFamily="Fraunces, Georgia, serif" fontWeight="700" fontSize={label.length > 8 ? 9 : 11} fill={trim}>
        {label.toUpperCase()}
      </text>
    </svg>
  )
}
