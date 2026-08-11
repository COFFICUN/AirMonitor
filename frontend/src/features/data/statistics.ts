export interface DescriptiveStatistics {
  readonly count: number;
  readonly minimum: number | null;
  readonly maximum: number | null;
  readonly mean: number | null;
  readonly median: number | null;
}

export function calculateStatistics(values: readonly (number | null)[]): DescriptiveStatistics {
  const finite = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (finite.length === 0) {
    return { count: 0, minimum: null, maximum: null, mean: null, median: null };
  }
  const sorted = [...finite].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 === 0
    ? (sorted[middle - 1]! + sorted[middle]!) / 2
    : sorted[middle]!;
  return {
    count: sorted.length,
    minimum: sorted[0]!,
    maximum: sorted.at(-1)!,
    mean: sorted.reduce((sum, value) => sum + value, 0) / sorted.length,
    median,
  };
}
