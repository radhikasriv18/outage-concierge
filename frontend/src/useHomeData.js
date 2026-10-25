import { useEffect, useState } from 'react'
import { getHome, getHomes } from './api'

// Loads the map homes and the selected home's answer card.
// `params` holds scenario inputs like { wind, crews }; pass {} for the backend defaults.
export default function useHomeData(params = {}) {
  const [homes, setHomes] = useState([])
  // ?home=043748782 in the URL preselects a home (handy for demo links).
  const [selectedId, setSelectedId] = useState(() => new URLSearchParams(window.location.search).get('home'))
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const paramKey = JSON.stringify(params)

  useEffect(() => {
    let ignore = false
    getHomes(params)
      .then((data) => !ignore && setHomes(data))
      .catch((e) => !ignore && setError(`Could not load homes: ${e.message}`))
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

  return { homes, selectedId, setSelectedId, detail, loading, error }
}
