/** Parse an optional price filter value as a decimal number.
 * Empty input means "no restriction" (null); malformed input is NaN so the
 * caller can reject it instead of silently dropping it.
 */
export function parsePrice(value?: string): number | null {
  if (value === undefined || value === null || value.trim() === '') return null
  const text = value.trim()
  if (!/^-?\d*\.?\d+$/.test(text)) return Number.NaN
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

/** Validate the optional product price-range filters.
 * Returns a user-facing message when the values cannot be sent to the API.
 */
export function validatePriceRange(min?: string, max?: string): string | null {
  const minimum = parsePrice(min)
  const maximum = parsePrice(max)

  if (Number.isNaN(minimum) || Number.isNaN(maximum)) {
    return 'Please enter a valid price.'
  }
  if ((minimum !== null && minimum < 0) || (maximum !== null && maximum < 0)) {
    return 'Price must be greater than or equal to 0.'
  }
  if (minimum !== null && maximum !== null && minimum > maximum) {
    return 'Minimum price cannot be greater than maximum price.'
  }
  return null
}
