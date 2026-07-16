import { afterEach, describe, expect, it, vi } from 'vitest'

import { AUTH_EXPIRED_EVENT, UnauthorizedError, authApi, getJSON, postJSON } from './client'

function failWith(status: number, statusText: string, body: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body, { status, statusText })),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('API error messages', () => {
  it('surfaces the backend detail as the error message', async () => {
    failWith(409, 'Conflict', JSON.stringify({ error: 'HTTP_409', detail: 'Set DRUKS_ENDPOINT.' }))
    await expect(postJSON('/api/x', {})).rejects.toThrow('Set DRUKS_ENDPOINT.')
  })

  it('falls back to the status line when the body is not JSON detail', async () => {
    failWith(502, 'Bad Gateway', '<html>proxy error</html>')
    await expect(postJSON('/api/x', {})).rejects.toThrow('502 Bad Gateway: <html>proxy error</html>')
  })
})

describe('session identity', () => {
  it('types a 401 and broadcasts the expiry', async () => {
    failWith(401, 'Unauthorized', JSON.stringify({ error: 'HTTP_401', detail: 'Sign in.' }))
    const expired = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, expired)
    try {
      await expect(getJSON('/api/x')).rejects.toBeInstanceOf(UnauthorizedError)
      expect(expired).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener(AUTH_EXPIRED_EVENT, expired)
    }
  })

  it('reads a dead session as null without broadcasting noise elsewhere', async () => {
    failWith(401, 'Unauthorized', JSON.stringify({ error: 'HTTP_401', detail: 'Sign in.' }))
    await expect(authApi.session()).resolves.toBeNull()
  })
})
