export function friendly(e: unknown): string {
  if (e instanceof Error) {
    return e.message
  }
  if (typeof e === 'string') {
    return e
  }
  return 'An unexpected error occurred. Please try again.'
}
