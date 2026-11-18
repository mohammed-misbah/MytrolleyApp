import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'
import { ApiError } from '@/services/apiClient'

/** One human-readable message for a failed API request.
 * Field-specific messages from the backend take priority over the generic
 * envelope message, so a single toast explains the actual conflict.
 */
export function serverErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const specific = Object.values(error.fields)
      .flat()
      .filter(Boolean)
    if (specific.length) return specific.join(' ')
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'The request could not be completed.'
}

/** Map backend ``error.fields`` onto React Hook Form field errors so the
 * message appears beneath the input that caused the failure. Returns whether
 * any field errors were applied. */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
): boolean {
  if (!(error instanceof ApiError)) return false
  const entries = Object.entries(error.fields).filter(([, messages]) => messages?.length)
  if (!entries.length) return false
  for (const [field, messages] of entries) {
    setError(field as Path<T>, { type: 'server', message: messages.join(' ') })
  }
  return true
}
