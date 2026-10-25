import { useMemo, useState } from 'react'
import { getNeighbor } from '../api'

// Offer the closest homes as "neighbors" so nobody has to type an ID.
function nearestHomes(homes, home, count = 5) {
  if (!home) return []
  return homes
    .filter((h) => h.home_id !== home.home_id)
    .map((h) => ({ ...h, d: (h.lat - home.lat) ** 2 + (h.lon - home.lon) ** 2 }))
    .sort((a, b) => a.d - b.d)
    .slice(0, count)
}

function pct(p) {
  return typeof p === 'number' ? `${Math.round(p * 100)}%` : '?'
}

export default function NeighborCheck({ homes, homeId, params }) {
  const home = homes.find((h) => h.home_id === homeId)
  const neighbors = useMemo(() => nearestHomes(homes, home), [homes, home])
  // '' means "let the backend pick the closest home on a different line".
  const [neighborId, setNeighborId] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function compare() {
    setError(null)
    setResult(null)
    try {
      setResult(await getNeighbor(homeId, neighborId, params))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 text-sm">
      <p className="font-medium text-gray-900">Why does my neighbor have power and I don’t?</p>
      <div className="flex flex-wrap gap-2">
        <select
          value={neighborId}
          onChange={(e) => setNeighborId(e.target.value)}
          className="min-w-0 rounded-lg border border-gray-200 bg-white px-2 py-2"
          aria-label="Pick a neighbor"
        >
          <option value="">Closest neighbor on a different line</option>
          {neighbors.map((n) => (
            <option key={n.home_id} value={n.home_id}>
              Neighbor {n.home_id}
            </option>
          ))}
        </select>
        <button
          onClick={compare}
          className="rounded-lg border border-gray-200 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
        >
          Compare
        </button>
      </div>
      {result && (
        <div className="space-y-2 rounded-lg bg-gray-50 px-3 py-3 text-gray-700">
          <p>{result.explanation}</p>
          {result.neighbor && (
            <p className="text-xs text-gray-500">
              Your chance: {pct(result.my_probability)} · Neighbor {result.neighbor}: {pct(result.neighbor_probability)}
            </p>
          )}
        </div>
      )}
      {error && <p className="text-red-600">Could not compare: {error}</p>}
    </div>
  )
}
