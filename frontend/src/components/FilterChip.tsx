/**
 * FilterChip — toggle-style chip used in active-filters rows (history,
 * research history, etc). Active when ``current === value``.
 */
interface FilterChipProps<T extends string> {
  value: T
  current: T
  onSelect: (next: T) => void
  label: string
  disabled?: boolean
}

export function FilterChip<T extends string>({
  value,
  current,
  onSelect,
  label,
  disabled = false,
}: FilterChipProps<T>) {
  return (
    <button
      type="button"
      className={`filter-chip ${current === value ? 'active' : ''}`}
      onClick={() => onSelect(value)}
      disabled={disabled}
    >
      {label}
    </button>
  )
}
