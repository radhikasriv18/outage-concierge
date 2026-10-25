import { useEffect, useState } from 'react'
import { getMessages } from '../api'

const TYPE_LABELS = {
  pre_storm: 'Before the storm',
  outage_confirmed: 'Outage confirmed',
  estimate_updated: 'Time updated',
  restored: 'Power back on',
}

export default function AlertMessages({ homeId }) {
  const [messages, setMessages] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false
    getMessages(homeId)
      .then((data) => !ignore && setMessages(data))
      .catch((e) => !ignore && setError(e.message))
    return () => {
      ignore = true
    }
  }, [homeId])

  if (error) return <p className="text-red-600">Could not load messages: {error}</p>

  return (
    <div className="space-y-2 pt-2">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Text messages you would get</p>
      {messages.map((m) => (
        <div key={m.type} className="max-w-md rounded-2xl rounded-bl-sm bg-gray-50 px-3 py-2">
          <p className="text-xs text-gray-400">{TYPE_LABELS[m.type] || m.type}</p>
          <p className="text-gray-700">{m.text}</p>
        </div>
      ))}
    </div>
  )
}
