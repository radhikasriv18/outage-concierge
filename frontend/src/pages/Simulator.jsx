import { useEffect, useState } from 'react'
import { getAudit, getBacktest } from '../api'
import AnswerCard from '../components/AnswerCard'
import HomeMap from '../components/HomeMap'
import useHomeData from '../useHomeData'
import { HomeSearch } from './MainScreen'

function Slider({ label, value, onChange, min, max, unit }) {
  return (
    <label className="block">
      <span className="flex justify-between text-sm text-gray-700">
        <span>{label}</span>
        <span>
          {value} {unit}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-accent-500"
      />
    </label>
  )
}

function StaffView({ detail }) {
  const [audit, setAudit] = useState([])
  useEffect(() => {
    getAudit().then(setAudit).catch(() => setAudit([]))
  }, [detail])

  return (
    <div className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 text-sm">
      <h2 className="font-medium text-gray-900">Staff view</h2>
      {detail ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-700">
          <dt className="text-gray-400">Home</dt>
          <dd>{detail.home_id}</dd>
          <dt className="text-gray-400">Risk / confidence</dt>
          <dd>
            {detail.risk?.band} / {detail.risk?.confidence}
          </dd>
          <dt className="text-gray-400">Restore hours</dt>
          <dd>
            {detail.restoration?.min_hours}–{detail.restoration?.max_hours}
          </dd>
          <dt className="text-gray-400">Repair line position</dt>
          <dd>#{detail.restoration?.queue_position}</dd>
          <dt className="text-gray-400">Alert / escalate</dt>
          <dd>
            {detail.alert?.eligible ? 'Yes' : 'No'} / {detail.alert?.escalate ? 'Yes' : 'No'}
          </dd>
          <dt className="text-gray-400">Fallback</dt>
          <dd>{detail.fallback ? 'Yes' : 'No'}</dd>
        </dl>
      ) : (
        <p className="text-sm text-gray-600">Pick a home to see its details.</p>
      )}
      <h3 className="pt-2 text-xs font-medium uppercase tracking-wide text-gray-400">Audit log</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-gray-600">
          <thead>
            <tr className="border-b border-gray-100 text-gray-400">
              <th className="py-1 pr-2 font-medium">Time</th>
              <th className="py-1 pr-2 font-medium">Home</th>
              <th className="py-1 pr-2 font-medium">Action</th>
              <th className="py-1 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {audit.map((row, i) => (
              <tr key={i} className="border-b border-gray-100 align-top">
                <td className="py-1 pr-2 whitespace-nowrap">{new Date(row.time).toLocaleString()}</td>
                <td className="pr-2">{row.home_id}</td>
                <td className="pr-2">{row.action}</td>
                <td>{row.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Backtest() {
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    getBacktest().then(setResult).catch((e) => setError(e.message))
  }, [])

  return (
    <div className="space-y-2 rounded-xl border border-gray-200 bg-white p-5 text-sm">
      <h2 className="font-medium text-gray-900">Tested on a real storm</h2>
      {error && <p className="text-red-600">Could not load backtest: {error}</p>}
      {result && (
        <>
          <p>
            Storm: <b>{result.storm}</b> · {result.damage_records} damage records
          </p>
          <p className="text-3xl font-semibold text-accent-600">{result.within_range_pct}%</p>
          <p>{result.summary}</p>
        </>
      )}
    </div>
  )
}

const HANDLING = [
  {
    title: 'Privacy',
    text: 'Homes are shown by anonymous IDs only, with no names or addresses. Life-support homes are not marked on the map. The AI assistant only sees our estimate numbers, never personal data.',
  },
  {
    title: 'Safety',
    text: 'Safety messages are clearly marked. We always tell people to stay away from fallen wires and to call 911 in an emergency.',
  },
  {
    title: 'Uncertainty',
    text: 'We give a time range, not an exact time, and say how sure we are. Estimates are kept separate from confirmed facts. When we lack data, we say so.',
  },
  {
    title: 'Limits',
    text: 'The data has no weather, so storm strength is a scenario input. Household details are synthetic and labeled. Repair records have dates only, not hours.',
  },
]

export default function Simulator() {
  const [wind, setWind] = useState(45)
  const [crews, setCrews] = useState(5)
  const { homes, selectedId, setSelectedId, detail, error } = useHomeData({ wind, crews })

  return (
    <div className="space-y-4">
      <div className="grid gap-6 rounded-xl border border-gray-200 bg-white p-5 md:grid-cols-2">
        <Slider label="Storm wind speed" value={wind} onChange={setWind} min={0} max={90} unit="mph" />
        <Slider label="Repair crews available" value={crews} onChange={setCrews} min={1} max={20} unit="crews" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="flex h-[50vh] flex-col gap-2 lg:h-[70vh]">
          <HomeSearch homes={homes} onSelect={setSelectedId} />
          <HomeMap homes={homes} selectedId={selectedId} onSelect={setSelectedId} powerPath={detail?.power_path} />
        </section>
        <section className="space-y-4">
          {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          {detail ? (
            <AnswerCard detail={detail} />
          ) : (
            <p className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-gray-500">
              Pick a home, then move the sliders to see the answer change.
            </p>
          )}
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <StaffView detail={detail} />
        <Backtest />
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5 text-sm">
        <h2 className="mb-3 font-medium text-gray-900">How we handle privacy, safety, uncertainty, and limits</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {HANDLING.map((h) => (
            <div key={h.title} className="rounded-lg bg-gray-50 p-4 text-gray-600">
              <h3 className="mb-1 font-medium text-gray-900">{h.title}</h3>
              <p>{h.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
