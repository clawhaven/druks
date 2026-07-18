# Owns every run nobody asked for: crons, background work. Seeded at first
# start; no provider email ever collides with it.
SYSTEM_ACCOUNT_ID = "system"

# A signed-in session in Redis: token -> account_id.
SESSION_PREFIX = "druks:session:"
