# A host leases for a fixed span; drukbox reaps it when the lease lapses, so a
# run whose worker dies frees its VM with no druks-side sweep. The lease must
# outlast any single continuous hold: agent calls are capped at
# MAX_AGENT_TIMEOUT_SECONDS, and a warm host rotates before its remaining lease
# can no longer cover one more worst-case call.
MAX_AGENT_TIMEOUT_SECONDS = 65 * 60  # 65 min — the existing sandbox-run horizon
SANDBOX_HOST_LEASE_SECONDS = 150 * 60  # 150 min — fits two back-to-back worst-case calls
SANDBOX_HOST_ROTATE_BEFORE_SECONDS = MAX_AGENT_TIMEOUT_SECONDS + 10 * 60  # 75 min (65 + 10 margin)
