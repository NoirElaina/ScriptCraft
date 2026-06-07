import { requestJson } from './client'

export interface AuthUser {
  id: number
  username: string
  email: string
  created_at: string
}

export interface AuthTokenResponse {
  expires_at: string
  user: AuthUser
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
}

export interface LoginPayload {
  identifier: string
  password: string
}

export async function register(payload: RegisterPayload): Promise<AuthTokenResponse> {
  return requestJson<AuthTokenResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function login(payload: LoginPayload): Promise<AuthTokenResponse> {
  return requestJson<AuthTokenResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getCurrentUser(): Promise<AuthUser> {
  return requestJson<AuthUser>('/api/auth/me')
}

export async function logout(): Promise<void> {
  await requestJson<void>('/api/auth/logout', { method: 'POST' })
}
