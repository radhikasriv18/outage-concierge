import { useEffect } from 'react'
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { placeName } from '../places'

const RISK_COLORS = { Low: '#4ade80', Medium: '#fbbf24', High: '#f87171' }
// Homes with no power path in AEP's data come back as risk_band 'Unknown'.
const UNKNOWN_COLOR = '#9ca3af'

function FitToHomes({ homes }) {
  const map = useMap()
  const count = homes.length
  useEffect(() => {
    if (count) map.fitBounds(homes.map((h) => [h.lat, h.lon]), { padding: [30, 30] })
    // Only refit when the set of homes changes size, not on every recolor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count, map])
  return null
}

// Moves the map to a searched street or home. `focus` is a new object on every search.
function FocusOn({ focus }) {
  const map = useMap()
  useEffect(() => {
    if (!focus?.points?.length) return
    if (focus.points.length === 1) map.flyTo(focus.points[0], 17)
    else map.flyToBounds(focus.points, { padding: [40, 40], maxZoom: 17 })
  }, [focus, map])
  return null
}

export default function HomeMap({ homes, selectedId, onSelect, powerPath, focus }) {
  // When a street is searched, its homes stay bright and the rest fade.
  const streetIds = focus?.ids

  return (
    <div className="flex h-full flex-col gap-2">
      <MapContainer center={[37.27, -79.94]} zoom={13} preferCanvas className="min-h-80 flex-1 rounded-xl border border-gray-200">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitToHomes homes={homes} />
        <FocusOn focus={focus} />
        {powerPath?.length > 1 && <Polyline positions={powerPath} pathOptions={{ color: '#60a5fa', weight: 4 }} />}
        {homes.map((h) => {
          const selected = h.home_id === selectedId
          const faded = streetIds && !streetIds.has(h.home_id) && !selected
          return (
            <CircleMarker
              key={h.home_id}
              center={[h.lat, h.lon]}
              radius={selected ? 11 : 7}
              pathOptions={{
                color: selected ? '#374151' : '#ffffff',
                weight: selected ? 3 : 1,
                opacity: faded ? 0.25 : 1,
                fillColor: RISK_COLORS[h.risk_band] || UNKNOWN_COLOR,
                fillOpacity: faded ? 0.25 : 0.9,
              }}
              eventHandlers={{ click: () => onSelect(h.home_id) }}
            >
              <Tooltip>
                {placeName(h) || `Home ${h.home_id}`}: {RISK_COLORS[h.risk_band] ? `${h.risk_band} risk` : 'No prediction'}
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>
      <div className="flex flex-wrap gap-4 text-xs text-gray-500">
        {Object.entries(RISK_COLORS).map(([band, color]) => (
          <span key={band} className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} /> {band} risk
          </span>
        ))}
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: UNKNOWN_COLOR }} /> No prediction
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-5 bg-blue-400" /> Your power path
        </span>
      </div>
    </div>
  )
}
