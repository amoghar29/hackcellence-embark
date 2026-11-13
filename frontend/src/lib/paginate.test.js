import test from 'node:test'
import assert from 'node:assert/strict'
import { paginate } from './paginate.js'

test('slices a page', () => {
  assert.deepEqual(paginate([1, 2, 3, 4, 5], 2, 2), { items: [3, 4], page: 2, pages: 3, total: 5 })
})
test('clamps page', () => {
  assert.equal(paginate([1, 2, 3], 99, 2).page, 2)
  assert.equal(paginate([1, 2, 3], 0, 2).page, 1)
})
test('empty list has one empty page', () => assert.deepEqual(paginate([], 1, 5), { items: [], page: 1, pages: 1, total: 0 }))
