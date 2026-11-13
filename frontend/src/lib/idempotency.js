// One Idempotency-Key per package (keyed by its selection), so a retried booking replays instead of booking twice.
export function bookingKey() {
  const keys = new Map()
  return {
    get(id) { if (!keys.has(id)) keys.set(id, crypto.randomUUID()); return keys.get(id) },
    clear() { keys.clear() },
  }
}
