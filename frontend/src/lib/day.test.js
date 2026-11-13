import test from 'node:test'
import assert from 'node:assert/strict'
import { dayView, photoSections } from './day.js'

const H1 = { item_id: 'hotel-1', type: 'hotel', name: 'Ginza Pearl', start: '2027-04-10', end: '2027-04-13', price_inr: 30000, details: { image: '/h1.jpg', rating: 8.6, nights: 3 } }
const H2 = { item_id: 'hotel-2', type: 'hotel', name: 'Kyoto Inn', start: '2027-04-13', end: '2027-04-16', price_inr: 24000, details: { image: '/h2.jpg', nights: 3 } }
const A1 = { item_id: 'attraction-A1', type: 'attraction', name: 'Senso-ji', start: '2027-04-11T10:00', end: '2027-04-11T11:30', price_inr: 0, details: { image: '/a1.jpg', visit_minutes: 90 } }
const A2 = { item_id: 'attraction-A2', type: 'attraction', name: 'Ueno Park', start: '2027-04-11T13:00', end: '2027-04-11T15:00', price_inr: 1200, details: { image: '/a2.jpg', visit_minutes: 120 } }
const F1 = { item_id: 'flight-arrival', type: 'flight', name: 'NS 432', start: '2027-04-09T20:00', end: '2027-04-10T07:20', price_inr: 90000, details: { duration_minutes: 470 } }
const T1 = { item_id: 'transfer-city-1', type: 'transfer', name: 'Shinkansen', start: '2027-04-13T09:00', end: '2027-04-13T11:15', price_inr: 8000, details: { duration_minutes: 135 } }
const pkg = {
  items: [F1, H1, A1, A2, T1, H2],
  days: [
    { date: '2027-04-11', day_type: 'FULL', city: 'Tokyo', events: [
      { time: '10:00', kind: 'ATTRACTION', item_id: 'attraction-A1', title: 'Senso-ji' },
      { time: '13:00', kind: 'ATTRACTION', item_id: 'attraction-A2', title: 'Ueno Park' }] },
    { date: '2027-04-13', day_type: 'CITY_CHANGE', city: 'Kyoto', events: [
      { time: '11:00', kind: 'CHECK_OUT', item_id: 'hotel-1', title: 'Check out' },
      { time: '09:00', kind: 'TRANSFER', item_id: 'transfer-city-1', title: 'Shinkansen' },
      { time: '15:00', kind: 'CHECK_IN', item_id: 'hotel-2', title: 'Check in' }] },
  ],
}

test('dayView: full day starts and ends at the hotel, sums visit time and cost', () => {
  const v = dayView(pkg, pkg.days[0])
  assert.equal(v.startAt.name, 'Ginza Pearl')
  assert.equal(v.endAt.name, 'Ginza Pearl')
  assert.deepEqual(v.events.map(e => e.minutes), [90, 120])
  assert.equal(v.visitMinutes, 210)
  assert.equal(v.travelMinutes, 0)
  assert.equal(v.cost, 1200)
  assert.equal(v.spanMinutes, 300) // 10:00 -> 15:00
  assert.deepEqual(v.photos.map(p => p.path), ['/a1.jpg', '/a2.jpg', '/h1.jpg'])
})

test('dayView: city-change day starts at the old hotel, ends at the new one, counts travel', () => {
  const v = dayView(pkg, pkg.days[1])
  assert.equal(v.startAt.name, 'Ginza Pearl')
  assert.equal(v.endAt.name, 'Kyoto Inn')
  assert.equal(v.travelMinutes, 135)
  assert.equal(v.events.find(e => e.kind === 'TRANSFER').minutes, 135)
  assert.equal(v.events.find(e => e.kind === 'CHECK_OUT').minutes, null)
})

test('photoSections: one scrolling strip per section, unique photos, empty sections dropped', () => {
  const s = photoSections({ items: [H1, H2, A1, A2, F1, { ...A1, item_id: 'dup' }] })
  assert.deepEqual(s.map(x => x.type), ['hotel', 'attraction'])
  assert.deepEqual(s[1].photos.map(p => p.path), ['/a1.jpg', '/a2.jpg'])
  assert.equal(s[0].photos[0].rating, 8.6)
})
