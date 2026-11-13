import test from 'node:test'
import assert from 'node:assert/strict'

const store = new Map()
globalThis.sessionStorage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) }
const { saveResults, loadResults, loadPicks, loadPackage, savePackage, badgesFor, travelText, SORTS, PICKS } = await import('./results.js')

const a = { total_inr: 300, travel_minutes: 900, avg_stars: 3.5, nights: 6 }
const b = { total_inr: 200, travel_minutes: 1200, avg_stars: 4, nights: 6 }
const c = { total_inr: 250, travel_minutes: 600, avg_stars: 3, nights: 6 }
const found = { count: 3, packages: [a, b, c], picks: { cheapest: 1, fastest: 2, best_rated: 1 } }

test.beforeEach(() => store.clear())

test('results keep the packages and the picks', () => {
  saveResults(found)
  assert.deepEqual(loadResults(), [a, b, c])
  assert.deepEqual(loadPicks(), found.picks)
})

test('a single package (search) has no picks', () => {
  saveResults(a)
  assert.deepEqual(loadResults(), [a])
  assert.deepEqual(loadPicks(), {})
})

test('nothing saved: empty list and no picks', () => {
  assert.deepEqual(loadResults(), [])
  assert.deepEqual(loadPicks(), {})
  assert.equal(loadPackage(0), null)
})

test('a package is its position; an edited copy wins until a new search', () => {
  saveResults(found)
  assert.deepEqual(loadPackage(1), b)
  const edited = { ...b, total_inr: 210 }
  savePackage(1, edited)
  assert.deepEqual(loadPackage(1), edited)
  assert.deepEqual(loadPackage(0), a)
  saveResults(found)
  assert.deepEqual(loadPackage(1), b)
})

test('badges: one package can win several picks, in a fixed order', () => {
  assert.deepEqual(badgesFor(found.picks, 1), ['cheapest', 'best_rated'])
  assert.deepEqual(badgesFor(found.picks, 2), ['fastest'])
  assert.deepEqual(badgesFor(found.picks, 0), [])
  assert.deepEqual(badgesFor({}, 0), [])
})

test('every pick has a label and a reason', () => {
  assert.deepEqual(Object.keys(PICKS), ['cheapest', 'fastest', 'best_rated'])
  for (const [label, why] of Object.values(PICKS)) assert.ok(label && why)
})

test('travel time reads as hours and minutes', () => {
  assert.equal(travelText(900), '15h')
  assert.equal(travelText(605), '10h 05m')
  assert.equal(travelText(45), '45m')
})

test('sorts: fastest and best rated order the list', () => {
  assert.deepEqual([a, b, c].sort(SORTS.fastest[1]), [c, a, b])
  assert.deepEqual([a, b, c].sort(SORTS.best_rated[1]), [b, a, c])
  assert.deepEqual([a, b, c].sort(SORTS.cheapest[1]), [b, c, a])
})
