import mock from './mock.json'

// Talks to the real backend by default. Set VITE_USE_MOCK=true in .env.local to use mock.json instead.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options) {
  const res = await fetch(API_URL + path, options)
  if (!res.ok) {
    // FastAPI puts a friendly sentence in `detail` (e.g. "We couldn't find home ...").
    const body = await res.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `${res.status} ${res.statusText}`
    throw new Error(detail)
  }
  return res.json()
}

function query(params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return entries.length ? '?' + new URLSearchParams(entries).toString() : ''
}

// `params` everywhere below is the storm scenario: { wind, crews }. Leave it out for the real Feb 2025 storm.

export function getHomes(params) {
  if (USE_MOCK) {
    return Promise.resolve(
      mock.homes.map(({ home_id, lat, lon, street, city, ...h }) => {
        const probability = mockProbability(h, params)
        return { home_id, lat, lon, street, city, risk_band: band(probability), probability }
      }),
    )
  }
  return request('/homes' + query(params))
}

export function getHome(homeId, params) {
  if (USE_MOCK) return Promise.resolve(mockDetail(homeId, params))
  return request(`/homes/${encodeURIComponent(homeId)}` + query(params))
}

// Leave `neighborId` empty and the backend picks the closest home on a different line.
export function getNeighbor(homeId, neighborId, params) {
  if (USE_MOCK) return Promise.resolve(mockNeighbor(homeId, neighborId))
  return request('/neighbor' + query({ home: homeId, neighbor: neighborId, wind: params?.wind }))
}

export function getMessages(homeId, params) {
  if (USE_MOCK) return Promise.resolve(mockMessages(homeId))
  return request(`/messages/${encodeURIComponent(homeId)}` + query(params))
}

export function sendChat(homeId, question, params) {
  if (USE_MOCK) {
    return Promise.resolve({
      answer: `(Demo answer) For ${homeId}: never run a generator indoors or in a garage. Keep it at least 20 feet from doors and windows.`,
    })
  }
  return request('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ home_id: homeId, question, ...params }),
  })
}

export function getRules() {
  if (USE_MOCK) return Promise.resolve(mock.rules)
  return request('/rules')
}

export function getWeather() {
  if (USE_MOCK) return Promise.resolve(mock.weather)
  return request('/weather')
}

export function getBacktest() {
  if (USE_MOCK) return Promise.resolve(mock.backtest)
  return request('/backtest')
}

export function getAudit() {
  if (USE_MOCK) {
    return Promise.resolve([
      { time: '2025-02-15T21:04:00', home_id: '043748782', action: 'risk_estimate', detail: 'High (42%), Fairly sure, wind 56 mph, crews 10' },
      { time: '2025-02-15T21:05:00', home_id: '043748782', action: 'chat_question', detail: 'Is my generator safe?' },
      { time: '2025-02-15T21:06:00', home_id: '337574651', action: 'fallback', detail: 'Missing equipment details' },
    ])
  }
  return request('/audit')
}

// ---------- mock helpers (shapes copied from the real backend) ----------

export const DEFAULT_WIND = mock.weather.slider_default_mph
export const DEFAULT_CREWS = 2 // matches backend engine.DEFAULT_CREWS (calibrated to AEP's real repair records)
const FALLBACK_HOME = '337574651'

function mockProbability(home, params = {}) {
  const wind = Number(params.wind ?? DEFAULT_WIND)
  const p = home._score * 0.5 + (wind - DEFAULT_WIND) / 100
  return Math.round(Math.min(0.95, Math.max(0.01, p)) * 1000) / 1000
}

function band(p) {
  return p >= 0.3 ? 'High' : p >= 0.1 ? 'Medium' : 'Low'
}

function clock(hoursFromNow) {
  const d = new Date(Date.now() + hoursFromNow * 3600 * 1000)
  return d.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })
}

function mockDetail(homeId, params = {}) {
  const home = mock.homes.find((h) => h.home_id === homeId)
  if (!home) throw new Error(`We couldn't find home ${homeId} in the demo area.`)
  if (homeId === FALLBACK_HOME) {
    return {
      home_id: homeId,
      street: home.street,
      city: home.city,
      fallback: "We can't predict this home reliably right now, because we don't have details about the equipment that feeds it.",
      actions: ['SAFETY: Stay far away from fallen power lines and report them to AEP'],
    }
  }
  const p = mockProbability(home, params)
  const b = band(p)
  const wind = Math.round(params.wind ?? DEFAULT_WIND)
  const crews = Number(params.crews ?? DEFAULT_CREWS)
  const min = Math.round(home._repair_hours * 0.5 * (DEFAULT_CREWS / crews) * 10) / 10
  const max = Math.round(home._repair_hours * 1.5 * (DEFAULT_CREWS / crews) * 10) / 10
  const pct = Math.round(p * 100)

  return {
    home_id: home.home_id,
    street: home.street,
    city: home.city,
    headline: {
      High: 'Your power is at high risk of going out during this storm.',
      Medium: 'Your power might go out during this storm.',
      Low: 'Your power will probably stay on during this storm.',
    }[b],
    risk: {
      band: b,
      probability: p,
      confidence: home._line === 'B' ? 'Somewhat sure' : 'Fairly sure',
      doubts: home._line === 'B' ? ['Your home is close to the line between two risk levels'] : [],
      reasons: [
        `Strong wind gusts of about ${wind} mph are expected`,
        home._line === 'C' ? 'Your power lines are underground' : 'Your power lines are above ground, where wind and trees can reach them',
        'The most at-risk part of your power path is a safety switch on your neighborhood line',
      ],
    },
    restoration: {
      range_text: `${clock(min)} – ${clock(max)}`,
      min_hours: min,
      max_hours: max,
      queue_position: home._line === 'A' ? 5 : home._line === 'B' ? 9 : 14,
      what_changes_it: [
        `If 5 more crews arrive: about ${Math.round(min * 0.7)} to ${Math.round(max * 0.7)} hours`,
        'If winds are 10 mph weaker: your chance of losing power drops',
      ],
    },
    facts: [`Storm scenario: wind gusts of about ${wind} mph in your area`, 'Your power lines are above ground (from AEP records)'],
    estimates: [
      `${b} chance of losing power (about ${pct}%).`,
      `If your power goes out, it should be back between ${clock(min)} and ${clock(max)}`,
    ],
    actions: [
      'Charge your phone and a backup battery now',
      'Keep a flashlight handy (avoid candles)',
      'SAFETY: Stay far away from fallen power lines, even if they look dead, and report them to AEP',
    ],
    alert: {
      eligible: b !== 'Low',
      channel: b === 'Low' ? null : 'Text message',
      timing: b === 'High' ? '12 hours before the storm' : b === 'Medium' ? '6 hours before the storm' : null,
      reason: b === 'Low' ? 'Low risk: no alert needed' : `${b} risk of losing power`,
      escalate: false,
      escalate_reasons: [],
    },
    power_path: [[home.lat, home.lon], mock.line_taps[home._line], mock.substation],
    fallback: null,
    profile_is_synthetic: true,
  }
}

function mockNeighbor(homeId, neighborId) {
  const a = mock.homes.find((h) => h.home_id === homeId)
  const b = neighborId
    ? mock.homes.find((h) => h.home_id === neighborId)
    : mock.homes.find((h) => h._line !== a?._line)
  if (!a || !b) throw new Error('We couldn’t find that home in the demo area.')
  const same = a._line === b._line
  return {
    home: a.home_id,
    neighbor: b.home_id,
    same_line: same,
    shared_equipment: same ? 5 : 2,
    my_probability: mockProbability(a),
    neighbor_probability: mockProbability(b),
    explanation: same
      ? "You and your neighbor get power through exactly the same equipment, so you'll almost always lose and regain power together."
      : 'You and your neighbor are on different safety switches, and you share the bigger equipment upstream (2 pieces).',
  }
}

function mockMessages(homeId) {
  return [
    { type: 'pre_storm', text: `AEP: A strong storm arrives tonight. Your power (${homeId}) is at high risk. Charge your phone now.` },
    { type: 'outage_confirmed', text: 'AEP: Your power is out. Crews are on the way. Stay away from fallen lines.' },
    { type: 'estimate_updated', text: "AEP: Update: more damage was found on your line. We're sorry for the delay." },
    { type: 'restored', text: "AEP: Your power is back. If it's still out at your home, reply OUT or call AEP." },
  ]
}
