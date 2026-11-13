import test from 'node:test'
import assert from 'node:assert/strict'
import { mapsLink, legOf, backLegOf, coordsOf, dayRoute, attractionsByDay, addMinutes, dayJourney } from './legs.js'

const HOTEL = { item_id: 'hotel-1', type: 'hotel', name: 'Ginza Pearl', catalog_id: 'HTL-1', city: 'Tokyo', start: '2027-04-10', end: '2027-04-13', details: { lat: 35.67, lng: 139.76 } }
const A1 = { item_id: 'attraction-A1', type: 'attraction', name: 'Senso-ji', catalog_id: 'A1', city: 'Tokyo', start: '2027-04-11T10:00', end: '2027-04-11T11:30',
  details: { lat: 35.71, lng: 139.79, travel_from: { name: 'Ginza Pearl', lat: 35.67, lng: 139.76, minutes: 30, km: 6.4, source: 'estimate' }, travel_back: null } }
const A2 = { item_id: 'attraction-A2', type: 'attraction', name: 'Ueno Park', catalog_id: 'A2', city: 'Tokyo', start: '2027-04-11T12:30', end: '2027-04-11T14:30',
  details: { lat: 35.71, lng: 139.77, travel_from: { name: 'Senso-ji', lat: 35.71, lng: 139.79, minutes: 15, km: 2.1, source: 'google' },
    travel_back: { name: 'Ginza Pearl', lat: 35.67, lng: 139.76, minutes: 25, km: 5.0, source: 'google' } } }
const A3 = { item_id: 'attraction-A3', type: 'attraction', name: 'Old', catalog_id: 'A3', city: 'Tokyo', start: '2027-04-12T10:00', end: '2027-04-12T11:00', details: {} }
const pkg = { items: [HOTEL, A2, A1, A3] }

test('mapsLink: Google Maps directions without a key', () => {
  assert.equal(mapsLink({ lat: 1.5, lng: 2 }, { lat: 3, lng: 4.25 }),
    'https://www.google.com/maps/dir/?api=1&origin=1.5,2&destination=3,4.25&travelmode=driving')
})

test('legOf: where the traveler comes from, with a directions link; null for old packages', () => {
  const l = legOf(A2)
  assert.deepEqual([l.from, l.minutes, l.km, l.estimate], ['Senso-ji', 15, 2.1, false])
  assert.equal(l.link, mapsLink({ lat: 35.71, lng: 139.79 }, { lat: 35.71, lng: 139.77 }))
  assert.equal(legOf(A1).estimate, true)
  assert.equal(legOf(A3), null)
  assert.equal(legOf(HOTEL), null)
})

test('backLegOf: the way back to the hotel after the last visit of the day', () => {
  const b = backLegOf(A2)
  assert.deepEqual([b.to, b.minutes], ['Ginza Pearl', 25])
  assert.equal(b.link, mapsLink({ lat: 35.71, lng: 139.77 }, { lat: 35.67, lng: 139.76 }))
  assert.equal(backLegOf(A1), null)
})

test('coordsOf: coordinates by catalog id from the package, skipping places without them', () => {
  assert.deepEqual(coordsOf(pkg), { 'HTL-1': { lat: 35.67, lng: 139.76 }, A1: { lat: 35.71, lng: 139.79 }, A2: { lat: 35.71, lng: 139.77 } })
})

test('dayRoute: hotel, visits by time, hotel again; empty on a day without visits', () => {
  const r = dayRoute(pkg, '2027-04-11')
  assert.deepEqual(r.map(p => p.item.item_id), ['hotel-1', 'attraction-A1', 'attraction-A2', 'hotel-1'])
  assert.deepEqual([r[1].lat, r[1].lng], [35.71, 139.79])
  assert.deepEqual(dayRoute(pkg, '2027-04-14'), [])
})

test('attractionsByDay: every visit grouped by date in time order, with the city', () => {
  const g = attractionsByDay(pkg)
  assert.deepEqual(g.map(d => [d.date, d.city, d.items.map(i => i.name)]),
    [['2027-04-11', 'Tokyo', ['Senso-ji', 'Ueno Park']], ['2027-04-12', 'Tokyo', ['Old']]])
})

test('addMinutes: clock arithmetic on HH:MM, wrapping at midnight', () => {
  assert.equal(addMinutes('10:00', -15), '09:45')
  assert.equal(addMinutes('23:50', 20), '00:10')
  assert.equal(addMinutes('00:05', -10), '23:55')
})

test('dayJourney: leave the hotel in time for the first visit, back after the last; null without legs', () => {
  const j = dayJourney([A2, A1])  // any order: the day is read by start time
  assert.deepEqual(j.leave, { time: '09:30', place: 'Ginza Pearl' })  // 10:00 - 30 min
  assert.deepEqual(j.back, { time: '14:55', place: 'Ginza Pearl' })   // 14:30 + 25 min
  assert.deepEqual(j.stops.map(s => [s.from, s.to.name]), [['Ginza Pearl', 'Senso-ji'], ['Senso-ji', 'Ueno Park']])
  assert.equal(dayJourney([A3]), null)
  assert.equal(dayJourney([]), null)
})
