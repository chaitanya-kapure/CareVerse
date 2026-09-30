/**
 * Query retry policy.
 *
 * The app-wide default retries a failed request once, which is right for a
 * flaky network and wrong for a refused one. A `403 NO_PATIENT_ACCESS` or a
 * `404 DOCUMENT_NOT_FOUND` is a decision the server reached deliberately and
 * will reach identically on the next attempt -- the patient has still not
 * authorized this doctor, and the document still is not theirs. Retrying it
 * cannot succeed, so it only does two unhelpful things: it doubles the number
 * of requests made against the authorization endpoint, and it delays the
 * "you do not have access" message by a second, during which the screen sits
 * on a spinner that will never resolve into anything but a refusal.
 *
 * So retries are for the failures that *can* be transient -- no response at
 * all, or a server-side fault -- and never for a client error.
 */

/** True when a failure is worth a second identical attempt. */
export function isWorthRetrying(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;

  const status = (error as { response?: { status?: number } })?.response?.status;

  // No response means the request never reached the server, or the connection
  // dropped. A 5xx is the server failing at its own end. Both can succeed on a
  // retry, so both are retried -- once, never in a loop.
  if (status === undefined || status >= 500) return true;

  // Everything else is a 4xx: the answer is the answer.
  return false;
}
