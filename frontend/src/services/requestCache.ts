/** Small in-memory GET cache with in-flight request deduplication.
 *
 * Reference data (categories, stores, dashboard summary) uses a short TTL.
 * Every GET is deduplicated while in flight, which removes the Strict Mode and
 * cross-component duplicates without serving stale data after mutations.
 *
 * Correctness rules:
 * - an epoch is bumped whenever auth or data changes; responses started before
 *   the bump can never write into the new cache generation;
 * - in-flight promises are dropped on invalidation, so a new user can never
 *   receive the previous user's pending response;
 * - keys are scoped to the active user/session.
 */

type Entry = { data: unknown; expires: number }
const cache = new Map<string, Entry>()
const inflight = new Map<string, Promise<unknown>>()
let epoch = 0
let scope = 'anon'

function scoped(key: string): string {
  return `${scope}|${key}`
}

function unscoped(key: string): string {
  const separator = key.indexOf('|')
  return separator === -1 ? key : key.slice(separator + 1)
}

/** Switch the cache generation to a different user/session. */
export function setCacheScope(nextScope: string): void {
  if (nextScope === scope) return
  scope = nextScope
  epoch += 1
  cache.clear()
  inflight.clear()
}

function run<T>(rawKey: string, fetcher: () => Promise<T>, ttlMs: number): Promise<T> {
  const key = scoped(rawKey)
  const startedInEpoch = epoch

  if (ttlMs > 0) {
    const hit = cache.get(key)
    if (hit && hit.expires > Date.now()) return Promise.resolve(hit.data as T)
  }
  const pending = inflight.get(key)
  if (pending) return pending as Promise<T>

  const promise = fetcher()
    .then((data) => {
      if (startedInEpoch === epoch) {
        if (ttlMs > 0) cache.set(key, { data, expires: Date.now() + ttlMs })
      }
      return data
    })
    .finally(() => {
      // Never delete a newer promise that replaced this key after invalidation.
      if (inflight.get(key) === promise) inflight.delete(key)
    })
  inflight.set(key, promise)
  return promise
}

/** Deduplicate simultaneous identical requests without caching the result. */
export function dedupGet<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  return run(key, fetcher, 0)
}

/** Cache stable reference data for a short period. */
export function cachedGet<T>(key: string, fetcher: () => Promise<T>, ttlMs = 30_000): Promise<T> {
  return run(key, fetcher, ttlMs)
}

export function invalidateCache(prefix?: string): void {
  epoch += 1
  inflight.clear()
  for (const key of [...cache.keys()]) {
    if (!prefix || unscoped(key).startsWith(prefix)) cache.delete(key)
  }
}
