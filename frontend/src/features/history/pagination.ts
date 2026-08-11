export function appendUniqueById<T extends { readonly id: number }>(
  current: readonly T[],
  incoming: readonly T[],
  maximumItems: number,
): readonly T[] {
  const seen = new Set(current.map(({ id }) => id));
  const merged = [...current];
  for (const item of incoming) {
    if (!seen.has(item.id) && merged.length < maximumItems) {
      seen.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

