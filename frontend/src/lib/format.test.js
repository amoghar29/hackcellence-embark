import test from 'node:test'
import assert from 'node:assert/strict'
import { money, parseBudget, duration, fmtDate, fmtTime, imageUrl } from './format.js'

test('money uses Indian grouping', () => {
  assert.equal(money(350000), '₹3,50,000')
  assert.equal(money(0), '₹0')
  assert.equal(money(-1200), '-₹1,200')
})
test('parseBudget accepts typed forms, rejects junk', () => {
  assert.equal(parseBudget('3,50,000'), 350000)
  assert.equal(parseBudget('₹ 10000'), 10000)
  assert.equal(parseBudget(''), null)
  assert.equal(parseBudget('abc'), null)
  assert.equal(parseBudget('1e5'), null)
  assert.equal(parseBudget(12.5), 12.5)
})
test('duration', () => {
  assert.equal(duration(45), '45m')
  assert.equal(duration(120), '2h')
  assert.equal(duration(125), '2h 05m')
})
test('dates and times', () => {
  assert.equal(fmtDate('2027-04-10'), '10 Apr 2027')
  assert.equal(fmtDate('2027-04-10T14:30'), '10 Apr 2027')
  assert.equal(fmtDate(null), '')
  assert.equal(fmtTime('2027-04-10T14:30'), '14:30')
})
test('imageUrl', () => {
  assert.equal(imageUrl('/images/hotels/a.jpg', 'http://x:8000'), 'http://x:8000/images/hotels/a.jpg')
  assert.equal(imageUrl('https://cdn/a.jpg', 'http://x:8000'), 'https://cdn/a.jpg')
  assert.equal(imageUrl(null, 'http://x:8000'), null)
})
