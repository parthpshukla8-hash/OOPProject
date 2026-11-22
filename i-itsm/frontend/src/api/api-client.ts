// Boundary translation: the API speaks snake_case, the front end speaks camelCase.
const TOKEN_STORAGE_KEY = 'iitsm.token'

export class ApiError extends Error {
  status: number
  code: string
  extra: Record<string, unknown>
  constructor(status: number, code: string, message: string, extra: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.extra = extra
  }
}

const toCamelKey = (key: string) => key.replace(/_([a-z0-9])/g, (_, character: string) => character.toUpperCase())
const toSnakeKey = (key: string) => key.replace(/[A-Z]/g, (character) => `_${character.toLowerCase()}`)

export function convertKeys(value: unknown, convertKey: (key: string) => string): unknown {
  if (Array.isArray(value)) return value.map((item) => convertKeys(item, convertKey))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, inner]) => [convertKey(key), convertKeys(inner, convertKey)]),
    )
  }
  return value
}
export const camelizeKeys = <T,>(value: unknown) => convertKeys(value, toCamelKey) as T
export const snakeizeKeys = (value: unknown) => convertKeys(value, toSnakeKey)

export const authToken = {
  get: () => localStorage.getItem(TOKEN_STORAGE_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_STORAGE_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_STORAGE_KEY),
}

let handleUnauthorized: () => void = () => undefined
export const onUnauthorized = (handler: () => void) => { handleUnauthorized = handler }

export type Params = Record<string, string | number | boolean | null | undefined>

async function request<T>(method: string, path: string, body?: unknown, params?: Params): Promise<T> {
  const query = new URLSearchParams()
  Object.entries(snakeizeKeys(params ?? {}) as Params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  const url = `/api${path}${query.toString() ? `?${query}` : ''}`
  const token = authToken.get()
  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(snakeizeKeys(body)),
    })
  } catch {
    throw new ApiError(0, 'network_failure', 'Cannot reach the server. Check your connection and try again.')
  }
  if (response.status === 204) return undefined as T
  const payload = camelizeKeys<Record<string, unknown>>(await response.json().catch(() => ({})))
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login/') handleUnauthorized()
    const { detail, code, ...extra } = payload as { detail?: string; code?: string }
    throw new ApiError(response.status, code ?? 'error', detail ?? 'Something went wrong.', extra)
  }
  return payload as T
}

export const api = {
  get: <T,>(path: string, params?: Params) => request<T>('GET', path, undefined, params),
  post: <T,>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  patch: <T,>(path: string, body: unknown) => request<T>('PATCH', path, body),
  put: <T,>(path: string, body: unknown) => request<T>('PUT', path, body),
  delete: <T,>(path: string) => request<T>('DELETE', path),
}
