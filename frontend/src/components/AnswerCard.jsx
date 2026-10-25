import { useState } from 'react'
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

function List({ items }) {
  if (!items?.length) return <p className="text-gray-400">Nothing to show.</p>
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-gray-400" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

function Label({ children }) {
  return <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-gray-400">{children}</p>
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

function QuestionAnswer({ which, detail }) {
  const { risk, restoration, alert } = detail
  if (which === 'power') {
    return (
      <div>
        <Label>Why we think this</Label>
        <List items={risk.reasons} />
      </div>
    )
  }
  if (which === 'time') {
    return (
      <div className="space-y-4">
        <div>
          <Label>Our estimate, not a promise</Label>
          <p>
            If your power goes out, it should be back between{' '}
            <span className="font-medium text-gray-900">{restoration.range_text}</span> ({restoration.min_hours}–
            {restoration.max_hours} hours).
          </p>
        </div>
        <RepairLine position={restoration.queue_position} />
        <div>
          <Label>What could change this</Label>
          <List items={restoration.what_changes_it} />
        </div>
      </div>
    )
  }
  if (which === 'todo') {
    return (
      <div className="space-y-3">
        <p className="rounded-md bg-red-50 px-3 py-2 text-red-800">
          <span className="font-medium">Safety:</span> stay away from fallen wires. Call 911 if someone is in danger.
        </p>
        <List items={detail.actions} />
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <p className="text-gray-900">
        {alert.eligible ? 'Yes, we will send you alerts.' : 'Not right now. We will alert you if your risk goes up.'}
      </p>
      <p className="text-gray-500">Reason: {alert.reason}</p>
      {alert.escalate && <p>A team member will also check on this home.</p>}
      <AlertMessages key={detail.home_id} homeId={detail.home_id} />
    </div>
  )
}

export default function AnswerCard({ detail }) {
  const [which, setWhich] = useState('power')
  const band = detail.risk?.band

  return (
    <div className="space-y-3 text-sm">
      {detail.fallback && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
          <p className="font-medium">We are not sure about this one.</p>
          <p>{detail.fallback}</p>
        </div>
      )}

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
          <QuestionAnswer which={which} detail={detail} />
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
      </div>
    </div>
  )
}
