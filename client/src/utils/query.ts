 /** Query retry policy. */

/** True when a failure is worth a second identical attempt. */
export function isWorthRetrying(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;

  const status = (error as { response?: { status?: number } })?.response?.status;
  const code = (error as { response?: { data?: { code?: string } } })?.response?.data
    ?.code;

  // A `503 SUMMARY_PROVIDER_UNAVAILABLE` is the one 5xx that is a decision
  if (code === "SUMMARY_PROVIDER_UNAVAILABLE") return false;

  // No response means the request never reached the server, or the connection
  if (status === undefined || status >= 500) return true;

  // Everything else is a 4xx: the answer is the answer.
  return false;
}
