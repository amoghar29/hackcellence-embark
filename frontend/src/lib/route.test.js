import test from 'node:test'
import assert from 'node:assert/strict'
import { parseHash, packageHash, reservationHash } from './route.js'

test('parseHash', () => {
  assert.deepEqual(parseHash(''), { name: 'home' })
  assert.deepEqual(parseHash('#/'), { name: 'home' })
  assert.deepEqual(parseHash('#/package/abc-1'), { name: 'package', id: 'abc-1' })
  assert.deepEqual(parseHash('#package/abc-1'), { name: 'package', id: 'abc-1' })
  assert.deepEqual(parseHash('#/reservation/4829105736'), { name: 'reservation', ref: '4829105736' })
  assert.deepEqual(parseHash('#/nope'), { name: 'home' })
  assert.deepEqual(parseHash('#/bookings'), { name: 'bookings' })
  assert.deepEqual(parseHash('#/find'), { name: 'find' })
})
test('builders round-trip', () => {
  assert.deepEqual(parseHash(packageHash('t9')), { name: 'package', id: 't9' })
  assert.deepEqual(parseHash(reservationHash('123')), { name: 'reservation', ref: '123' })
})
