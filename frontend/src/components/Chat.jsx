import { useState } from 'react'
import { sendChat } from '../api'

// One tap asks these. They cover what used to be separate sections on the page.
const SUGGESTIONS = [
  'What should I do now?',
  'Will I get alerts?',
  'Why does my neighbor have power and I don’t?',
  'Is my generator safe to use?',
]

export default function Chat({ homeId }) {
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [sending, setSending] = useState(false)

  async function ask(text) {
    const q = text.trim()
    if (!q || sending) return
    setQuestion('')
    setMessages((m) => [...m, { from: 'you', text: q }])
    setSending(true)
    try {
      const { answer } = await sendChat(homeId, q)
      setMessages((m) => [...m, { from: 'bot', text: answer }])
    } catch (err) {
      setMessages((m) => [...m, { from: 'bot', text: `Sorry, something went wrong (${err.message}). Please try again.` }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 text-sm">
      <div>
        <p className="font-medium text-gray-900">Ask a question</p>
        <p className="text-xs text-gray-400">Answers only use the numbers shown above. In an emergency, call 911.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => ask(s)}
            disabled={sending}
            className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:border-accent-200 hover:bg-accent-50 hover:text-accent-700 disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
      {(messages.length > 0 || sending) && (
        <div className="max-h-64 space-y-2 overflow-y-auto">
          {messages.map((m, i) => (
            <p
              key={i}
              className={`max-w-[85%] rounded-2xl px-3 py-2 ${
                m.from === 'you' ? 'ml-auto bg-accent-50 text-accent-700' : 'bg-gray-50 text-gray-700'
              }`}
            >
              {m.text}
            </p>
          ))}
          {sending && <p className="text-gray-400">Thinking…</p>}
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          ask(question)
        }}
        className="flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Or type your own question"
          className="min-w-0 flex-1 rounded-lg border border-gray-200 px-3 py-2 outline-none focus:border-accent-500"
          aria-label="Your question"
        />
        <button
          disabled={sending}
          className="rounded-lg bg-accent-500 px-4 py-2 font-medium text-white hover:bg-accent-600 disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </div>
  )
}
