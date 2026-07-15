import { afterEach, describe, expect, it, vi } from 'vitest'

import { onAuthExpired } from './authEvents'
import { UnauthorizedError, authApi, getJSON, postJSON } from './client'

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
  it('sends the session cookie on every call', async () => {
    const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(
      async () => new Response('{}', { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    await getJSON('/api/x')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: 'same-origin' })
  })

  it('types a 401 and broadcasts the expiry', async () => {
    failWith(401, 'Unauthorized', JSON.stringify({ error: 'HTTP_401', detail: 'Sign in.' }))
    const expired = vi.fn()
    const unsubscribe = onAuthExpired(expired)
    try {
      await expect(getJSON('/api/x')).rejects.toBeInstanceOf(UnauthorizedError)
      expect(expired).toHaveBeenCalledTimes(1)
    } finally {
      unsubscribe()
    }
  })

  it('reads a dead session as null without broadcasting noise elsewhere', async () => {
    failWith(401, 'Unauthorized', JSON.stringify({ error: 'HTTP_401', detail: 'Sign in.' }))
    await expect(authApi.session()).resolves.toBeNull()
  })
})
