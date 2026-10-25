import mock from './mock.json'

// Set VITE_USE_MOCK=false in .env.local once the backend is running.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options) {
  const res = await fetch(API_URL + path, options)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

function query(params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  return entries.length ? '?' + new URLSearchParams(entries).toString() : ''
}

export function getHomes(params) {
  if (USE_MOCK) return Promise.resolve(mock.homes.map((h) => ({ ...h, risk_band: mockBand(h, params) })))
  return request('/homes' + query(params))
}

export function getHome(homeId, params) {
  if (USE_MOCK) return Promise.resolve(mockDetail(homeId, params))
  return request(`/homes/${encodeURIComponent(homeId)}` + query(params))
}

export function getNeighbor(homeId, neighborId) {
  if (USE_MOCK) return Promise.resolve(mockNeighbor(homeId, neighborId))
  return request('/neighbor' + query({ home: homeId, neighbor: neighborId }))
}

export function getMessages(homeId) {
  if (USE_MOCK) return Promise.resolve(mockMessages(homeId))
  return request(`/messages/${encodeURIComponent(homeId)}`)
}

export function sendChat(homeId, question) {
  if (USE_MOCK) {
    return Promise.resolve({
      answer: `(Demo answer) For ${homeId}: never run a generator indoors or in a garage. Keep it at least 20 feet from doors and windows.`,
    })
  }
  return request('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ home_id: homeId, question }),
  })
}

// Not in API.md yet — proposed to backend (see frontend/API_REQUESTS.md).
export function getBacktest() {
  if (USE_MOCK) {
    return Promise.resolve({
      storm: 'Feb 13–17, 2025',
      damage_records: 1223,
      within_range_pct: 78,
      summary: 'In 78 out of 100 repairs, the real repair finished inside our estimated range.',
    })
  }
  return request('/backtest')
}

export function getAudit() {
  if (USE_MOCK) {
    return Promise.resolve([
      { time: '2025-02-15T21:04:00', home_id: '043748782', action: 'risk_estimate', detail: 'High, wind 60 mph, crews 5' },
      { time: '2025-02-15T21:05:00', home_id: '043748782', action: 'chat', detail: 'Question passed input check' },
      { time: '2025-02-15T21:06:00', home_id: '337574651', action: 'fallback', detail: 'Missing network chain' },
    ])
  }
  return request('/audit')
}

// ---------- mock helpers ----------

const DEFAULT_WIND = 45
const DEFAULT_CREWS = 5

function mockScore(home, params = {}) {
  const wind = Number(params.wind ?? DEFAULT_WIND)
  return home._score + (wind - DEFAULT_WIND) / 60
}

function mockBand(home, params) {
  const s = mockScore(home, params)
  return s > 0.66 ? 'High' : s > 0.33 ? 'Medium' : 'Low'
}

function clock(hoursFromNow) {
  const d = new Date(Date.now() + hoursFromNow * 3600 * 1000)
  return d.toLocaleTimeString([], { hour: 'numeric' })
}

function mockDetail(homeId, params = {}) {
  const home = mock.homes.find((h) => h.home_id === homeId)
  if (!home) throw new Error('Home not found')
  const band = mockBand(home, params)
  const crews = Number(params.crews ?? DEFAULT_CREWS)
  const scale = DEFAULT_CREWS / Math.max(crews, 1)
  const min = Math.max(1, Math.round(home._repair_hours * 0.6 * scale))
  const max = Math.max(min + 1, Math.round(home._repair_hours * 1.5 * scale))
  const moreMin = Math.max(1, Math.round(home._repair_hours * 0.6 * (DEFAULT_CREWS / (crews + 2))))
  const moreMax = Math.max(moreMin + 1, Math.round(home._repair_hours * 1.5 * (DEFAULT_CREWS / (crews + 2))))
  const headline = {
    High: 'Your power will likely go out tonight.',
    Medium: 'Your power might go out tonight.',
    Low: 'Your power will probably stay on.',
  }[band]

  return {
    home_id: home.home_id,
    headline,
    risk: {
      band,
      confidence: band === 'Medium' ? 'Not very sure' : 'Fairly sure',
      reasons: [
        `Wind of about ${params.wind ?? DEFAULT_WIND} mph expected`,
        home._line === 'C' ? 'Underground wires' : 'Overhead wires',
        home._line === 'A' ? 'Damage on this line in past storms' : 'Little past damage on this line',
      ],
    },
    restoration: {
      range_text: `${clock(min)} – ${clock(max)}`,
      min_hours: min,
      max_hours: max,
      queue_position: home._line === 'A' ? 4 : home._line === 'B' ? 7 : 12,
      what_changes_it: [`2 more crews: ${moreMin}–${moreMax} hours`, 'More damage found: longer', 'Roads blocked: longer'],
    },
    facts: ['Storm warning for your area', `Your home gets power from line ${home._line}`],
    estimates: [`${band} chance of an outage tonight`, `If it goes out, power back in ${min}–${max} hours`],
    actions: ['Charge your phone and power banks', 'Keep a flashlight handy', 'Test your sump pump backup'],
    alert: {
      eligible: band !== 'Low',
      escalate: band === 'High',
      reason: band === 'Low' ? 'Low risk right now' : `${band} risk`,
    },
    power_path: [[home.lat, home.lon], mock.line_taps[home._line], mock.substation],
    fallback: home.home_id === '337574651' ? 'We do not have enough data about your power line to give a reliable estimate.' : null,
  }
}

function mockNeighbor(homeId, neighborId) {
  const a = mock.homes.find((h) => h.home_id === homeId)
  const b = mock.homes.find((h) => h.home_id === neighborId)
  if (!a || !b) throw new Error('Home not found')
  const same = a._line === b._line
  return {
    same_line: same,
    explanation: same
      ? 'You and your neighbor get power from the same line, so you will likely lose and get back power together.'
      : `Your home is on line ${a._line}. Your neighbor's home is on line ${b._line}. Damage on one line does not cut power on the other.`,
  }
}

function mockMessages(homeId) {
  return [
    { type: 'pre_storm', text: `AEP: Strong storm tonight. High outage risk for your home (${homeId}). Charge your phone now.` },
    { type: 'outage_confirmed', text: 'AEP: We know your power is out. Crews are on the way. Estimate: 2 AM – 10 AM.' },
    { type: 'estimate_updated', text: 'AEP: Update: more crews arrived. New estimate: 2 AM – 6 AM.' },
    { type: 'restored', text: 'AEP: Your power is back on. Still out? Reply OUT.' },
  ]
}
