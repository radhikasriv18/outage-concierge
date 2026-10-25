import { useEffect } from 'react'
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'

const RISK_COLORS = { Low: '#4ade80', Medium: '#fbbf24', High: '#f87171' }

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

export default function HomeMap({ homes, selectedId, onSelect, powerPath }) {
  return (
    <div className="flex h-full flex-col gap-2">
      <MapContainer center={[37.27, -79.94]} zoom={13} preferCanvas className="min-h-80 flex-1 rounded-xl border border-gray-200">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitToHomes homes={homes} />
        {powerPath?.length > 1 && <Polyline positions={powerPath} pathOptions={{ color: '#60a5fa', weight: 4 }} />}
        {homes.map((h) => {
          const selected = h.home_id === selectedId
          return (
            <CircleMarker
              key={h.home_id}
              center={[h.lat, h.lon]}
              radius={selected ? 11 : 7}
              pathOptions={{
                color: selected ? '#374151' : '#ffffff',
                weight: selected ? 3 : 1,
                fillColor: RISK_COLORS[h.risk_band] || '#9ca3af',
                fillOpacity: 0.9,
              }}
              eventHandlers={{ click: () => onSelect(h.home_id) }}
            >
              <Tooltip>
                {h.home_id}: {h.risk_band || 'Unknown'} risk
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
          <span className="inline-block h-0.5 w-5 bg-blue-400" /> Your power path
        </span>
      </div>
    </div>
  )
}
