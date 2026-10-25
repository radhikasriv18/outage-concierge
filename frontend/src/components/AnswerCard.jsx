import { useEffect, useState } from 'react'
import { getRules } from '../api'
import AlertMessages from './AlertMessages'

const BAND_PILL = {
  High: 'bg-red-50 text-red-700',
  Medium: 'bg-amber-50 text-amber-700',
  Low: 'bg-green-50 text-green-700',
}

const QUESTIONS = [
  { key: 'power', label: 'Will I lose power?' },
  { key: 'time', label: 'How long?' },
  { key: 'todo', label: 'What should I do?' },
  { key: 'alert', label: 'Will you alert me?' },
]

const SAFETY = 'SAFETY:'

function List({ items }) {
  if (!items?.length) return <p className="text-gray-400">Nothing to show.</p>
  return (
    <ul className="space-y-1.5">
      {items.map((item) =>
        item.startsWith(SAFETY) ? (
          <li key={item} className="rounded-md bg-red-50 px-3 py-2 text-red-800">
            <span className="font-medium">Safety:</span> {item.slice(SAFETY.length).trim()}
          </li>
        ) : (
          <li key={item} className="flex gap-2">
            <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-gray-400" />
            <span>{item}</span>
          </li>
        ),
      )}
    </ul>
  )
}

function Label({ children }) {
  return <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-gray-400">{children}</p>
}

function percent(p) {
  return typeof p === 'number' ? `about ${Math.round(p * 100)}%` : null
}

function RepairLine({ position }) {
  if (!position) return null
  const dots = Math.min(position, 15)
  return (
    <div>
      <Label>Your place in the repair line</Label>
      <div className="flex flex-wrap items-center gap-1" aria-hidden="true">
        {Array.from({ length: dots }, (_, i) => (
          <span
            key={i}
            className={`inline-block h-2.5 w-2.5 rounded-full ${i === dots - 1 ? 'bg-accent-500' : 'bg-gray-200'}`}
          />
        ))}
        <span className="ml-2 text-xs text-gray-500">you are #{position}</span>
      </div>
      <p className="mt-1 text-xs text-gray-500">{position - 1} repairs are ahead of yours.</p>
    </div>
  )
}

function AlertRules() {
  const [rules, setRules] = useState(null)
  useEffect(() => {
    getRules().then(setRules).catch(() => setRules(null))
  }, [])
  if (!rules?.alert_rules?.length) return null
  return (
    <details className="text-gray-600">
      <summary className="cursor-pointer text-xs text-gray-500">How we decide who gets alerts</summary>
      <div className="mt-2">
        <List items={rules.alert_rules} />
      </div>
    </details>
  )
}

function QuestionAnswer({ which, detail, params }) {
  const { risk = {}, restoration = {}, alert = {} } = detail
  if (which === 'power') {
    return (
      <div className="space-y-4">
        <p>
          Chance of losing power: <span className="font-medium text-gray-900">{percent(risk.probability) ?? risk.band}</span>
          <span className="text-gray-500"> · {risk.confidence}</span>
        </p>
        <div>
          <Label>Why we think this</Label>
          <List items={risk.reasons} />
        </div>
        {risk.doubts?.length > 0 && (
          <div>
            <Label>Why we’re not fully sure</Label>
            <List items={risk.doubts} />
          </div>
        )}
      </div>
    )
  }
  if (which === 'time') {
    return (
      <div className="space-y-4">
        <div>
          <Label>Our estimate, not a promise</Label>
          {restoration.range_text ? (
            <p>
              If your power goes out, it should be back between{' '}
              <span className="font-medium text-gray-900">{restoration.range_text}</span>
              {restoration.min_hours != null && (
                <span className="text-gray-500">
                  {' '}
                  ({Math.round(restoration.min_hours)}–{Math.round(restoration.max_hours)} hours)
                </span>
              )}
              .
            </p>
          ) : (
            <p>We can’t give a reliable restoration time for your home in this scenario.</p>
          )}
        </div>
        <RepairLine position={restoration.queue_position} />
        {restoration.what_changes_it?.length > 0 && (
          <div>
            <Label>What could change this</Label>
            <List items={restoration.what_changes_it} />
          </div>
        )}
      </div>
    )
  }
  if (which === 'todo') {
    return <List items={detail.actions} />
  }
  return (
    <div className="space-y-3">
      <p className="text-gray-900">
        {alert.eligible ? 'Yes, we will send you alerts.' : 'Not right now. We will alert you if your risk goes up.'}
      </p>
      {alert.eligible && (alert.channel || alert.timing) && (
        <p>
          <span className="text-gray-500">How:</span> {alert.channel}
          {alert.timing && (
            <>
              {' '}
              · <span className="text-gray-500">When:</span> {alert.timing}
            </>
          )}
        </p>
      )}
      <p className="text-gray-500">Reason: {alert.reason}</p>
      {alert.escalate && <p>A person at AEP will also check on this home.</p>}
      <AlertRules />
      <AlertMessages key={detail.home_id} homeId={detail.home_id} params={params} />
    </div>
  )
}

export default function AnswerCard({ detail, params }) {
  const [which, setWhich] = useState('power')
  const band = detail.risk?.band

  // Fallback homes come without risk, restoration, or alert (see API.md).
  if (detail.fallback) {
    return (
      <div className="space-y-3 text-sm">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-amber-600">Home {detail.home_id}</p>
            <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs font-medium text-gray-600">No prediction</span>
          </div>
          <p className="mt-2 text-xl font-semibold text-amber-900">
            {detail.headline || 'We are not sure about this one.'}
          </p>
          <p className="mt-1">{detail.fallback}</p>
        </div>
        <div className="space-y-4 rounded-xl border border-gray-200 bg-white p-5 text-gray-700">
          {detail.facts?.length > 0 && (
            <div>
              <Label>Confirmed</Label>
              <List items={detail.facts} />
            </div>
          )}
          {detail.actions?.length > 0 && (
            <div>
              <Label>What you can still do</Label>
              <List items={detail.actions} />
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3 text-sm">
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-gray-400">Home {detail.home_id}</p>
          {band && (
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${BAND_PILL[band] || 'bg-gray-100'}`}>
              {band} risk · {detail.risk.confidence}
            </span>
          )}
        </div>
        <p className="mt-2 text-xl font-semibold text-gray-900">{detail.headline}</p>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="flex flex-wrap gap-1 border-b border-gray-100 p-2">
          {QUESTIONS.map((q) => (
            <button
              key={q.key}
              onClick={() => setWhich(q.key)}
              className={`rounded-md px-3 py-1.5 ${
                which === q.key ? 'bg-accent-50 font-medium text-accent-700' : 'text-gray-500 hover:bg-gray-50'
              }`}
            >
              {q.label}
            </button>
          ))}
        </div>
        <div className="p-5 text-gray-700">
          <QuestionAnswer which={which} detail={detail} params={params} />
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <p className="mb-3 font-medium text-gray-900">At a glance</p>
        <div className="grid gap-4 text-gray-700 sm:grid-cols-2">
          <div>
            <Label>Confirmed</Label>
            <List items={detail.facts} />
          </div>
          <div>
            <Label>Our estimate</Label>
            <List items={detail.estimates} />
          </div>
        </div>
        {detail.profile_is_synthetic && (
          <p className="mt-4 text-xs text-gray-400">
            Household details (like a sump pump or medical device) are sample data for this demo.
          </p>
        )}
      </div>
    </div>
  )
}
