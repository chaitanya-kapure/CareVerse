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
 * all, or a server-side fault -- and never for a decision the server reached
 * deliberately, whether that decision arrived as a 4xx or as the one 5xx that
 * is really a refusal.
 */

/** True when a failure is worth a second identical attempt. */
export function isWorthRetrying(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;

  const status = (error as { response?: { status?: number } })?.response?.status;
  const code = (error as { response?: { data?: { code?: string } } })?.response?.data
    ?.code;

  // A `503 SUMMARY_PROVIDER_UNAVAILABLE` is the one 5xx that is a decision
  // rather than a fault. The server is healthy; this build simply has no
  // summarizer configured, and it will still have none in a second. Retrying
  // re-sends the identical request to get the identical refusal, and the
  // doctor waits through the delay before being told that somebody has to
  // change a setting on the server.
  if (code === "SUMMARY_PROVIDER_UNAVAILABLE") return false;

  // No response means the request never reached the server, or the connection
  // dropped. A 5xx is the server failing at its own end. Both can succeed on a
  // retry, so both are retried -- once, never in a loop.
  if (status === undefined || status >= 500) return true;

  // Everything else is a 4xx: the answer is the answer.
  return false;
}
