import { useMemo, useState } from 'react'
import { placeName } from '../places'

// One box for both: a street name ("Pollard") or a 9-digit home ID.
export default function HomeSearch({ homes, onSelect, onStreet }) {
  const [text, setText] = useState('')
  const [message, setMessage] = useState(null)

  // "Pollard, Vinton" -> homes on that street
  const streets = useMemo(() => {
    const byStreet = new Map()
    for (const h of homes) {
      const place = placeName(h)
      if (!place) continue
      if (!byStreet.has(place)) byStreet.set(place, [])
      byStreet.get(place).push(h)
    }
    return byStreet
  }, [homes])
  const labels = useMemo(() => [...streets.keys()].sort(), [streets])

  function search(e) {
    e.preventDefault()
    setMessage(null)
    const raw = text.trim()
    if (!raw) return

    // IDs are 9-digit strings that can start with 0, so compare as text, never as numbers.
    const digits = raw.replace(/\s/g, '')
    if (/^\d+$/.test(digits)) {
      const match = homes.find((h) => String(h.home_id) === digits)
      if (match) onSelect(match.home_id)
      else setMessage({ error: true, text: 'We couldn’t find that home ID. Check it and try again.' })
      return
    }

    const q = raw.toLowerCase()
    const label = labels.find((l) => l.toLowerCase() === q) ?? labels.find((l) => l.toLowerCase().startsWith(q))
    if (!label) {
      setMessage({ error: true, text: 'We couldn’t find that street in this area. Try picking one from the list.' })
      return
    }
    setText(label)
    const onThisStreet = streets.get(label)
    if (onThisStreet.length === 1) {
      onSelect(onThisStreet[0].home_id)
    } else {
      onStreet(onThisStreet)
      setMessage({ error: false, text: `${onThisStreet.length} homes on ${label}. Click yours on the map.` })
    }
  }

  return (
    <form onSubmit={search} className="flex flex-wrap items-center gap-2 text-sm">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        list="street-names"
        placeholder="Your street (like Pollard) or home ID"
        className="min-w-0 flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 outline-none focus:border-accent-500"
        aria-label="Your street or home ID"
      />
      <datalist id="street-names">
        {labels.map((l) => (
          <option key={l} value={l} />
        ))}
      </datalist>
      <button className="rounded-lg bg-accent-500 px-4 py-2 font-medium text-white hover:bg-accent-600">Find</button>
      {message && <p className={`w-full ${message.error ? 'text-red-600' : 'text-gray-600'}`}>{message.text}</p>}
    </form>
  )
}
