#!/usr/bin/env bash
# First-boot entrypoint. Mirrors the drukbox base entrypoint but seeds the
# non-root ``druks`` user instead of root — Claude Code refuses
# ``bypassPermissions`` under uid 0, so agents must SSH in unprivileged.
set -euo pipefail

: "${DRUKBOX_AUTHORIZED_KEY:?DRUKBOX_AUTHORIZED_KEY is required}"

install -d -m 700 -o druks -g druks /home/druks/.ssh
printf '%s\n' "$DRUKBOX_AUTHORIZED_KEY" > /home/druks/.ssh/authorized_keys
chmod 600 /home/druks/.ssh/authorized_keys
chown druks:druks /home/druks/.ssh/authorized_keys

# Persist caller-supplied env for SSH sessions: pam_env reads /etc/environment.
for name in ${DRUKBOX_ENV_KEYS:-}; do
  printf '%s=%s\n' "$name" "${!name-}" >> /etc/environment
done

ssh-keygen -A

exec /usr/sbin/sshd -D -e
