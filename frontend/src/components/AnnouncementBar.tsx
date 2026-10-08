import { openChat } from '../chatEvents'

// Scrolling "shop window" ticker under the nav. Every line is true of the store, and each one is a reason
// to keep shopping. Duplicated once so the loop is seamless; pauses on hover; still for reduced motion.
const MESSAGES = [
  '★ Officially licensed Yale apparel',
  '★ Gear for 11 residential colleges',
  '★ Live stock & sizes from our assistant',
  '★ Visit us at 57 Broadway, New Haven',
  '★ Hoodies, crewnecks, tees & quarter-zips',
]

export default function AnnouncementBar() {
  return (
    <div className="announce" role="region" aria-label="Store announcements">
      <div className="announce-viewport">
        <div className="announce-track">
          {[...MESSAGES, ...MESSAGES].map((m, i) => (
            <span key={i} aria-hidden={i >= MESSAGES.length}>
              {m}
            </span>
          ))}
        </div>
      </div>
      <button type="button" className="announce-cta" onClick={openChat}>
        Need a size? Ask us →
      </button>
    </div>
  )
}
