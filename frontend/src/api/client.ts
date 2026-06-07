import axios, { type AxiosRequestConfig } from 'axios'

export const apiClient = axios.create({
  baseURL: '/',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

export async function requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  try {
    const response = await apiClient.request<T>({
      url,
      method: init.method ?? 'GET',
      data: parseRequestBody(init.body),
      headers: init.headers as AxiosRequestConfig['headers'],
      signal: init.signal ?? undefined,
    })
    return response.data
  } catch (error) {
    throw new Error(readRequestErrorMessage(error))
  }
}

function parseRequestBody(body: BodyInit | null | undefined): unknown {
  if (body === undefined || body === null) return undefined
  if (typeof body !== 'string') return body

  try {
    return JSON.parse(body)
  } catch {
    return body
  }
}

function readRequestErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : '请求失败'
  }

  const payload = error.response?.data
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    return String(payload.detail)
  }
  if (typeof payload === 'string' && payload) {
    return payload
  }
  return error.message || '请求失败'
}
