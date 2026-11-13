import test from 'node:test'
import assert from 'node:assert/strict'
import { bookingKey } from './idempotency.js'

test('same trip reuses the key until cleared (retry of one click)', () => {
  const k = bookingKey()
  assert.equal(k.get('t1'), k.get('t1'))
})

test('clear gives a fresh key (new click after success or key-reused)', () => {
  const k = bookingKey()
  const a = k.get('t1'); k.clear()
  assert.notEqual(k.get('t1'), a)
})

test('different trip gets a different key', () => {
  const k = bookingKey()
  assert.notEqual(k.get('t1'), k.get('t2'))
})

test('key is 1-255 chars', () => {
  const key = bookingKey().get('t1')
  assert.ok(key.length >= 1 && key.length <= 255)
})
