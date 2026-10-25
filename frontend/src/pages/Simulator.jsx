import { useEffect, useState } from 'react'
import { DEFAULT_CREWS, DEFAULT_WIND, getAudit, getBacktest, getRules, getWeather } from '../api'
import AnswerCard from '../components/AnswerCard'
import HomeMap from '../components/HomeMap'
import useHomeData from '../useHomeData'
import { HomeSearch } from './MainScreen'

// Backend limits (see backend/main.py): wind 20–100 mph, crews 1–50.
const WIND_MIN = 20
const WIND_MAX = 100
const CREWS_MAX = 50

// The slider moves freely; the backend is only asked when the user lets go
// (a new wind/crews combination takes a few seconds to simulate).
function Slider({ label, value, onCommit, min, max, unit, note }) {
  const [draft, setDraft] = useState(value)
  const commit = () => draft !== value && onCommit(draft)

  return (
    <label className="block">
      <span className="flex justify-between text-sm text-gray-700">
        <span>{label}</span>
        <span>
          {draft} {unit}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        value={draft}
        onChange={(e) => setDraft(Number(e.target.value))}
        onPointerUp={commit}
        onKeyUp={commit}
        onBlur={commit}
        className="mt-2 w-full accent-accent-500"
      />
      {note && <span className="text-xs text-gray-400">{note}</span>}
    </label>
  )
}

function Row({ label, children }) {
  return (
    <>
      <dt className="text-gray-400">{label}</dt>
      <dd>{children}</dd>
    </>
  )
}

function StaffView({ detail }) {
  const [audit, setAudit] = useState([])
  const [rules, setRules] = useState(null)
  useEffect(() => {
    getAudit().then(setAudit).catch(() => setAudit([]))
  }, [detail])
  useEffect(() => {
    getRules().then(setRules).catch(() => setRules(null))
  }, [])

  const r = detail?.restoration
  return (
    <div className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 text-sm">
      <h2 className="font-medium text-gray-900">Staff view</h2>
      {detail ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-700">
          <Row label="Home">{detail.home_id}</Row>
          {detail.fallback ? (
            <Row label="Fallback">Yes: {detail.fallback}</Row>
          ) : (
            <>
              <Row label="Risk / probability">
                {detail.risk?.band} / {typeof detail.risk?.probability === 'number' ? detail.risk.probability.toFixed(3) : '—'}
              </Row>
              <Row label="Confidence">{detail.risk?.confidence}</Row>
              <Row label="Restore hours">{r?.min_hours != null ? `${r.min_hours}–${r.max_hours}` : '—'}</Row>
              <Row label="Repair line position">{r?.queue_position ? `#${r.queue_position}` : '—'}</Row>
              <Row label="Alert">
                {detail.alert?.eligible ? `Yes · ${detail.alert.channel} · ${detail.alert.timing}` : 'No'}
              </Row>
              <Row label="Escalate">
                {detail.alert?.escalate ? detail.alert.escalate_reasons?.join('; ') || 'Yes' : 'No'}
              </Row>
            </>
          )}
        </dl>
      ) : (
        <p className="text-gray-500">Pick a home to see its details.</p>
      )}

      {rules?.escalation_rules?.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs text-gray-500">Escalation rules</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-gray-600">
            {rules.escalation_rules.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </details>
      )}

      <h3 className="pt-2 text-xs font-medium uppercase tracking-wide text-gray-400">Audit log</h3>
      <div className="max-h-64 overflow-auto">
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
                <td className="py-1 pr-2 whitespace-nowrap">{new Date(row.time).toLocaleTimeString()}</td>
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

const STORM_NAMES = { feb2025: 'Feb 2025', sep2024: 'Sep 2024', jan2025: 'Jan 2025' }

function Backtest() {
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    getBacktest().then(setResult).catch((e) => setError(e.message))
  }, [])

  return (
    <div className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 text-sm">
      <h2 className="font-medium text-gray-900">Tested on real storms</h2>
      {error && <p className="text-red-600">Could not load backtest: {error}</p>}
      {result && (
        <>
          {typeof result.average_top10_lift === 'number' && (
            <p className="text-3xl font-semibold text-accent-600">{result.average_top10_lift.toFixed(1)}×</p>
          )}
          <p className="text-gray-700">{result.summary}</p>
          {result.method && <p className="text-xs text-gray-400">{result.method}</p>}
          {result.restoration_summary && (
            <div className="border-t border-gray-100 pt-3">
              <p className="font-medium text-gray-900">Repair times</p>
              <p className="text-gray-700">{result.restoration_summary}</p>
              {typeof result.restoration?.calibrated_within_48h === 'number' && (
                <p className="text-xs text-gray-400">
                  With {result.restoration.calibrated_crews} crews, our simulation finishes{' '}
                  {Math.round(result.restoration.calibrated_within_48h * 100)}% of repairs within 48 hours.{' '}
                  {result.restoration.note}
                </p>
              )}
            </div>
          )}
          {result.home_level_note && (
            <details className="text-xs text-gray-500">
              <summary className="cursor-pointer">Why we don’t score individual homes</summary>
              <p className="mt-1">{result.home_level_note}</p>
            </details>
          )}
          {result.per_storm?.length > 0 && (
            <table className="w-full text-left text-xs text-gray-600">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400">
                  <th className="py-1 pr-2 font-medium">Storm it never saw</th>
                  <th className="py-1 pr-2 font-medium">Top-10% lift</th>
                  <th className="py-1 font-medium">ROC AUC</th>
                </tr>
              </thead>
              <tbody>
                {result.per_storm.map((s) => (
                  <tr key={s.test_storm} className="border-b border-gray-100">
                    <td className="py-1 pr-2">{STORM_NAMES[s.test_storm] || s.test_storm}</td>
                    <td className="pr-2">{s.lift_top10}×</td>
                    <td>{s.roc_auc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}

const HANDLING = [
  {
    title: 'Privacy',
    text: 'Homes are shown by anonymous IDs only, with no names or addresses. Equipment locations are rounded to about 100 m. The AI assistant only sees our estimate numbers, never personal data.',
  },
  {
    title: 'Safety',
    text: 'Safety messages are clearly marked. We always tell people to stay away from fallen wires and to call 911 in an emergency.',
  },
  {
    title: 'Uncertainty',
    text: 'We give a chance and a time range, not exact promises, and say how sure we are and why. Estimates are kept separate from confirmed facts. When we lack data, we say so.',
  },
  {
    title: 'Limits',
    text: 'Weather comes from a public archive on a ~10 km grid. Household details are sample data and labeled. Repair records have dates only, not hours. Crew numbers are assumptions.',
  },
]

export default function Simulator() {
  const [wind, setWind] = useState(Math.round(DEFAULT_WIND))
  const [crews, setCrews] = useState(DEFAULT_CREWS)
  const [realGust, setRealGust] = useState(null)

  useEffect(() => {
    getWeather()
      .then((w) => setRealGust(Math.round(w.slider_default_mph)))
      .catch(() => setRealGust(null))
  }, [])

  const params = { wind, crews }
  const { homes, selectedId, setSelectedId, detail, loading, homesLoading, error } = useHomeData(params)
  const updating = loading || homesLoading

  return (
    <div className="space-y-4">
      <div className="relative grid gap-6 rounded-xl border border-gray-200 bg-white p-5 md:grid-cols-2">
        {updating && (
          <span className="absolute right-3 -top-2.5 rounded-full bg-accent-50 px-2.5 py-0.5 text-xs text-accent-700">
            Updating… (a new storm takes a few seconds)
          </span>
        )}
        <Slider
          label="Storm wind gusts"
          value={wind}
          onCommit={setWind}
          min={WIND_MIN}
          max={WIND_MAX}
          unit="mph"
          note={realGust ? `The real Feb 2025 storm averaged about ${realGust} mph.` : null}
        />
        <Slider label="Repair crews available" value={crews} onCommit={setCrews} min={1} max={CREWS_MAX} unit="crews" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="flex h-[50vh] flex-col gap-2 lg:h-[70vh]">
          <HomeSearch homes={homes} onSelect={setSelectedId} />
          <HomeMap homes={homes} selectedId={selectedId} onSelect={setSelectedId} powerPath={detail?.power_path} />
        </section>
        <section className="space-y-4">
          {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          {detail ? (
            <div className={updating ? 'opacity-50 transition-opacity' : 'transition-opacity'}>
              <AnswerCard detail={detail} params={params} />
            </div>
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
