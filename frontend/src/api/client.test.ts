import { afterEach, describe, expect, it, vi } from 'vitest'

import { postJSON } from './client'

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
