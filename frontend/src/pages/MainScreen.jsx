import AnswerCard from '../components/AnswerCard'
import Chat from '../components/Chat'
import HomeMap from '../components/HomeMap'
import HomeSearch from '../components/HomeSearch'
import useHomeData from '../useHomeData'

export default function MainScreen() {
  const { homes, selectedId, setSelectedId, detail, loading, error, focus, selectFromSearch, showStreet } = useHomeData()

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="flex h-[50vh] flex-col gap-2 lg:sticky lg:top-4 lg:h-[calc(100vh-8rem)]">
        <HomeSearch homes={homes} onSelect={selectFromSearch} onStreet={showStreet} />
        <HomeMap
          homes={homes}
          selectedId={selectedId}
          onSelect={setSelectedId}
          powerPath={detail?.power_path}
          focus={focus}
        />
      </section>

      <section className="space-y-3">
        {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        {!selectedId && (
          <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-gray-500">
            Type your street, then click your home on the map, to see if a storm will affect you.
          </div>
        )}
        {loading && !detail && <p className="text-sm text-gray-500">Loading…</p>}
        {detail && (
          <>
            <AnswerCard detail={detail} />
            <Chat key={`c-${detail.home_id}`} homeId={detail.home_id} />
          </>
        )}
      </section>
    </div>
  )
}
