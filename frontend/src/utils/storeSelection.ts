/** Frontend-only ordering of the three visible store cards. */

export function defaultVisibleStoreIds(ids: number[]): number[] {
  return ids.slice(0, 3)
}

export function reorderVisibleStoreIds(current: number[], selectedId: number): number[] {
  return [selectedId, ...current.filter((id) => id !== selectedId)].slice(0, 3)
}
