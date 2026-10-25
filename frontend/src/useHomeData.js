import { useEffect, useState } from 'react'
import { getHome, getHomes } from './api'

// Loads the map homes and the selected home's answer card.
// `params` holds scenario inputs like { wind, crews }; pass {} for the backend defaults.
export default function useHomeData(params = {}) {
  const [homes, setHomes] = useState([])
  // ?home=043748782 in the URL preselects a home (handy for demo links).
  const [selectedId, setSelectedId] = useState(() => new URLSearchParams(window.location.search).get('home'))
  const [detail, setDetail] = useState(null)
  const [homesLoading, setHomesLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const paramKey = JSON.stringify(params)

  useEffect(() => {
    let ignore = false
    setHomesLoading(true)
    getHomes(params)
      .then((data) => !ignore && setHomes(data))
      .catch((e) => !ignore && setError(`Could not load homes: ${e.message}`))
      .finally(() => !ignore && setHomesLoading(false))
    return () => {
      ignore = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramKey])

  useEffect(() => {
    if (!selectedId) return
    let ignore = false
    setLoading(true)
    setError(null)
    getHome(selectedId, params)
      .then((data) => !ignore && setDetail(data))
      .catch((e) => !ignore && setError(`Could not load this home: ${e.message}`))
      .finally(() => !ignore && setLoading(false))
    return () => {
      ignore = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, paramKey])

  // Where the map should move: a whole street (dots highlighted) or one home.
  const [focus, setFocus] = useState(null)
  function selectFromSearch(homeId) {
    setSelectedId(homeId)
    const h = homes.find((x) => x.home_id === homeId)
    if (h) setFocus({ points: [[h.lat, h.lon]] })
  }
  function showStreet(streetHomes) {
    setFocus({ points: streetHomes.map((h) => [h.lat, h.lon]), ids: new Set(streetHomes.map((h) => h.home_id)) })
  }

  return {
    homes, selectedId, setSelectedId, detail, loading, homesLoading, error,
    focus, selectFromSearch, showStreet,
  }
}
