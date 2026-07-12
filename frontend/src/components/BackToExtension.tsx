import { Link } from 'wouter'

import { extensionHome } from '../extensions/registry'

/**
 * Inline back link for extension-independent detail pages (/usage, /events).
 *
 * Those pages are reached from appbar pills and otherwise have no
 * obvious navigation back to a extension dashboard — operators pressed
 * Esc, got nothing, hunted for a close button, gave up. The Esc
 * handler in ``AppShell`` now routes back via the global keymap;
 * this component is the visible counterpart for operators who don't
 * know the shortcut.
 *
 * The extension is read from ``document.body.dataset.extension``, which
 * ``AppShell`` sets on every render, then resolved to its declared home
 * through the registry — so an extension with a custom ``home`` lands on
 * it, not a guessed ``/<name>``. The URL of a extension-independent page
 * (``/usage``, ``/events``) carries no extension signal of its own.
 */
export function BackToExtension() {
  const extension = document.body.dataset.extension
  if (!extension) return null
  return (
    <Link
      href={extensionHome(extension)}
      className="back-to-extension mono dim"
      title="back to dashboard (Esc)"
    >
      ← back to {extension}
    </Link>
  )
}
