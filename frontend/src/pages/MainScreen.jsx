import { useState } from 'react'
import AnswerCard from '../components/AnswerCard'
import Chat from '../components/Chat'
import HomeMap from '../components/HomeMap'
import NeighborCheck from '../components/NeighborCheck'
import useHomeData from '../useHomeData'

export function HomeSearch({ homes, onSelect }) {
  const [text, setText] = useState('')
  const [notFound, setNotFound] = useState(false)

  function search(e) {
    e.preventDefault()
    // IDs are 9-digit strings that can start with 0, so compare as text, never as numbers.
    const id = text.replace(/\s/g, '')
    const match = homes.find((h) => String(h.home_id) === id)
    setNotFound(!match)
    if (match) onSelect(match.home_id)
  }

  return (
    <form onSubmit={search} className="flex flex-wrap items-center gap-2 text-sm">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Home ID, like 043748782"
        inputMode="numeric"
        className="min-w-0 flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 outline-none focus:border-accent-500"
        aria-label="Home ID"
      />
      <button className="rounded-lg bg-accent-500 px-4 py-2 font-medium text-white hover:bg-accent-600">Find</button>
      {notFound && <p className="w-full text-red-600">We couldn’t find that home ID. Check it and try again.</p>}
    </form>
  )
}

export default function MainScreen() {
  const { homes, selectedId, setSelectedId, detail, loading, error } = useHomeData()

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="flex h-[50vh] flex-col gap-2 lg:sticky lg:top-4 lg:h-[calc(100vh-8rem)]">
        <HomeSearch homes={homes} onSelect={setSelectedId} />
        <HomeMap homes={homes} selectedId={selectedId} onSelect={setSelectedId} powerPath={detail?.power_path} />
      </section>

      <section className="space-y-3">
        {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        {!selectedId && (
          <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-gray-500">
            Click your home on the map, or type your home ID, to see if a storm will affect you.
          </div>
        )}
        {loading && !detail && <p className="text-sm text-gray-500">Loading…</p>}
        {detail && (
          <>
            <AnswerCard detail={detail} />
            <NeighborCheck key={`n-${detail.home_id}`} homes={homes} homeId={detail.home_id} />
            <Chat key={`c-${detail.home_id}`} homeId={detail.home_id} />
          </>
        )}
      </section>
    </div>
  )
}
