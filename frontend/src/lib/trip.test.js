import test from 'node:test'
import assert from 'node:assert/strict'
import { noResultView, altLabel, stopsInOrder, routeByDay, changeSummary, priceBreakdown, carouselPhotos, tripExport } from './trip.js'

test('NO_PACKAGE view uses blockers as typed reasons, keeps alternatives', () => {
  const v = noResultView({
    code: 'NO_PACKAGE', error: 'No flight', reasons: ['No flight'], suggestion: 'Start on 2027-04-04.',
    blockers: [{ code: 'NO_ARRIVAL_FLIGHT', part: 'flight', message: 'No flight from BOM lands in Japan on 2027-04-03.' }],
    alternatives: [{ change: { start_date: '2027-04-04' }, total_inr: 251200 }],
  })
  assert.equal(v.kind, 'NO_PACKAGE')
  assert.deepEqual(v.reasons, [{ text: 'No flight from BOM lands in Japan on 2027-04-03.', part: 'flight' }])
  assert.equal(v.suggestion, 'Start on 2027-04-04.')
  assert.deepEqual(v.alternatives[0], { label: 'Start on 4 Apr 2027', change: { start_date: '2027-04-04' }, total_inr: 251200 })
  assert.deepEqual(v.facts, [])
})
test('NO_PACKAGE without blockers falls back to reasons then error', () => {
  assert.deepEqual(noResultView({ code: 'NO_PACKAGE', error: 'E', reasons: ['a', 'b'], blockers: [] }).reasons.map(r => r.text), ['a', 'b'])
  assert.deepEqual(noResultView({ code: 'NO_PACKAGE', error: 'E' }).reasons.map(r => r.text), ['E'])
})
test('OVER_BUDGET view shows budget, cheapest and the gap', () => {
  const v = noResultView({ code: 'OVER_BUDGET', error: 'x', budget_inr: 10000, cheapest_total_inr: 266378, over_by_inr: 256378, suggestion: 's', alternatives: [] })
  assert.equal(v.kind, 'OVER_BUDGET')
  assert.deepEqual(v.facts, [
    { label: 'Your budget', value: '₹10,000' },
    { label: 'Cheapest trip', value: '₹2,66,378' },
    { label: 'Short by', value: '₹2,56,378' }])
})
test('altLabel', () => {
  assert.equal(altLabel({ departure_city: 'DEL' }), 'Fly from DEL')
  assert.equal(altLabel({ nights: 4 }), 'Take 4 nights')
  assert.equal(altLabel({ budget_inr: 266378 }), 'Raise budget to ₹2,66,378')
})

const pkg = {
  days: [
    { date: '2027-04-10', events: [{ kind: 'FLIGHT_ARRIVAL', item_id: 'f1', time: '08:00' }, { kind: 'CHECK_IN', item_id: 'h1', time: '15:00' }] },
    { date: '2027-04-11', events: [{ kind: 'ATTRACTION', item_id: 'a1', time: '10:00' }, { kind: 'ATTRACTION', item_id: 'a2', time: '14:00' }] },
    { date: '2027-04-12', events: [{ kind: 'CHECK_OUT', item_id: 'h1', time: '10:00' }, { kind: 'ATTRACTION', item_id: 'a3', time: '12:00' }] },
  ],
  items: [
    { item_id: 'h1', type: 'hotel', name: 'H', catalog_id: 'HTL-1' },
    { item_id: 'a1', type: 'attraction', name: 'A1', catalog_id: 'ATT-1' },
    { item_id: 'a2', type: 'attraction', name: 'A2', catalog_id: 'ATT-2' },
    { item_id: 'a3', type: 'attraction', name: 'A3', catalog_id: 'ATT-3' },
  ],
}
test('stopsInOrder: hotel at check-in, attractions by time, numbered, skips unknown coords', () => {
  const details = { 'HTL-1': { lat: 1, lng: 1 }, 'ATT-1': { lat: 2, lng: 2 }, 'ATT-3': { lat: 3, lng: 3 } }
  const s = stopsInOrder(pkg, details)
  assert.deepEqual(s.map(x => [x.n, x.item.item_id, x.date, x.time]), [[1, 'h1', '2027-04-10', '15:00'], [2, 'a1', '2027-04-11', '10:00'], [3, 'a3', '2027-04-12', '12:00']])
  assert.deepEqual([s[1].lat, s[1].lng], [2, 2])
})

test('changeSummary: replaced, removed, total delta', () => {
  const before = { total_inr: 100, items: [
    { item_id: 'h1', type: 'hotel', city: 'Kyoto', name: 'Old Inn', catalog_id: 'H1' },
    { item_id: 'f1', type: 'flight', city: 'Tokyo', name: 'AI 1', catalog_id: 'F1' },
    { item_id: 'a1', type: 'attraction', city: 'Kyoto', name: 'Temple', catalog_id: 'A1' }] }
  const after = { total_inr: 80, items: [
    { item_id: 'h9', type: 'hotel', city: 'Kyoto', name: 'New Inn', catalog_id: 'H9' },
    { item_id: 'f1', type: 'flight', city: 'Tokyo', name: 'AI 2', catalog_id: 'F2' }] }
  const s = changeSummary(before, after)
  assert.equal(s.delta, -20)
  assert.deepEqual(s.changed.map(c => [c.type, c.from, c.to]).sort(), [['attraction', 'Temple', null], ['flight', 'AI 1', 'AI 2'], ['hotel', 'Old Inn', 'New Inn']])
})
test('priceBreakdown sums by type', () => {
  assert.deepEqual(priceBreakdown([{ type: 'flight', price_inr: 5 }, { type: 'flight', price_inr: 7 }, { type: 'hotel', price_inr: 1 }]),
    { flight: 12, hotel: 1, transfer: 0, attraction: 0 })
})
test('carouselPhotos unique with titles', () => {
  const ph = carouselPhotos({ items: [
    { type: 'hotel', name: 'H', details: { image: '/i/a.jpg' } },
    { type: 'attraction', name: 'A', details: { image: '/i/a.jpg' } },
    { type: 'attraction', name: 'B', details: { image: '/i/b.jpg' } },
    { type: 'flight', name: 'F', details: {} }] })
  assert.deepEqual(ph, [{ path: '/i/a.jpg', title: 'H', type: 'hotel' }, { path: '/i/b.jpg', title: 'B', type: 'attraction' }])
})

test('tripExport keeps the trip format and drops UI-only fields', () => {
  const pkg = { status: 'BOOKED', reference: '1234567890', country: 'Japan', items: [{ item_id: 'i1' }], total_inr: 5, budget_inr: 9,
    request: {}, selection: {}, days: [], cities: [], nights: 6, remaining_inr: 4 }
  const out = tripExport(pkg)
  assert.deepEqual(Object.keys(out).sort(), ['budget_inr', 'country', 'items', 'reference', 'status', 'total_inr'])
  assert.equal(out.reference, '1234567890')
})

test('routeByDay: one line per day, each joined to the previous day\'s last stop', () => {
  const s = [{ date: 'a', lat: 1, lng: 1 }, { date: 'a', lat: 2, lng: 2 }, { date: 'b', lat: 3, lng: 3 }, { date: 'c', lat: 4, lng: 4 }]
  assert.deepEqual(routeByDay(s), [
    { date: 'a', pts: [[1, 1], [2, 2]] },
    { date: 'b', pts: [[2, 2], [3, 3]] },
    { date: 'c', pts: [[3, 3], [4, 4]] },
  ])
  assert.deepEqual(routeByDay([]), [])
})
