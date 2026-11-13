import test from 'node:test'
import assert from 'node:assert/strict'
import { validateSearch, toRequest } from './validate.js'

const rules = { min_nights: 3, max_nights: 10, first_night: '2027-04-01', last_departure: '2027-04-20' }
const ok = { departure_city: 'BLR', country: 'Japan', start_date: '2027-04-10', nights: 6, adults: 2, child_ages: [6], budget_inr: '3,50,000' }
const errs = patch => validateSearch({ ...ok, ...patch }, rules)

test('valid form has no errors', () => assert.deepEqual(errs({}), {}))
test('required fields', () => {
  const e = errs({ departure_city: '', country: '', start_date: '', budget_inr: '' })
  for (const f of ['departure_city', 'country', 'start_date', 'budget_inr']) assert.ok(e[f], f)
})
test('start date before first night', () => assert.ok(errs({ start_date: '2027-03-31' }).start_date))
test('trip must end by last departure, message names latest start', () => {
  const e = errs({ start_date: '2027-04-18', nights: 5 })
  assert.match(e.start_date, /15 Apr 2027/)
})
test('nights range and integer', () => {
  assert.ok(errs({ nights: 2 }).nights)
  assert.ok(errs({ nights: 11 }).nights)
  assert.ok(errs({ nights: 3.5 }).nights)
  assert.equal(errs({ nights: 3 }).nights, undefined)
})
test('adults at least 1', () => assert.ok(errs({ adults: 0 }).adults))
test('child ages 0-17 and present', () => {
  assert.ok(errs({ child_ages: [18] }).child_ages)
  assert.ok(errs({ child_ages: [''] }).child_ages)
  assert.equal(errs({ child_ages: [0, 17] }).child_ages, undefined)
})
test('budget must be positive integer', () => {
  assert.ok(errs({ budget_inr: '0' }).budget_inr)
  assert.ok(errs({ budget_inr: '12.5' }).budget_inr)
})
test('toRequest builds the API body', () => {
  assert.deepEqual(toRequest({ ...ok, nights: '6', adults: '2', child_ages: ['6'] }),
    { departure_city: 'BLR', country: 'Japan', start_date: '2027-04-10', nights: 6, adults: 2, child_ages: [6], budget_inr: 350000 })
})

test('departure city is free text: any city passes, blank or too long does not', () => {
  assert.equal(errs({ ...ok, departure_city: 'Paris' }).departure_city, undefined)
  assert.equal(errs({ ...ok, departure_city: 'New York' }).departure_city, undefined)
  assert.ok(errs({ ...ok, departure_city: '   ' }).departure_city)
  assert.ok(errs({ ...ok, departure_city: 'x'.repeat(61) }).departure_city)
})

test('toRequest sends picked cities and a non-mixed theme', () => {
  const body = toRequest({ ...ok, cities: ['Kyoto', 'Osaka'], theme: 'spiritual' })
  assert.deepEqual(body.cities, ['Kyoto', 'Osaka'])
  assert.equal(body.theme, 'spiritual')
})
test('toRequest leaves out no cities and the mixed theme', () => {
  const body = toRequest({ ...ok, cities: [], theme: 'mixed' })
  assert.equal('cities' in body, false)
  assert.equal('theme' in body, false)
})
