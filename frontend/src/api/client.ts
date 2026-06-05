const AUTH_TOKEN_KEY = 'scriptcraft.auth.token'

export function getAuthToken(): string {
  return window.localStorage.getItem(AUTH_TOKEN_KEY) ?? ''
}

export function setAuthToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token)
}

export function clearAuthToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
}

export async function requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const token = getAuthToken()
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })

  if (response.status === 204) {
    return undefined as T
  }

  const payload = await response.json()

  if (!response.ok) {
    if (response.status === 401) {
      clearAuthToken()
    }
    throw new Error(payload.detail ?? '请求失败')
  }

  return payload
}
