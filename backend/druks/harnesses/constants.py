# Redis keys for harness logins: a pending flow's state while the operator
# completes it, and the per-connection SET NX lock that serializes refresh.
LOGIN_PENDING_PREFIX = "druks:login:pending:"
REFRESH_LOCK_PREFIX = "druks:harness:refresh:"
