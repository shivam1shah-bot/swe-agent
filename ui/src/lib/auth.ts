/**
 * Authentication utilities for reading credentials from environment configuration.
 * Supports JWT (Bearer token) and Basic Auth (legacy fallback).
 */

/**
 * Get authentication credentials from environment configuration.
 * 
 * @returns Object containing username and password
 */
export async function getAuthCredentials(): Promise<{ username: string; password: string }> {
  try {
    // For now, we'll fetch the runtime config directly from the server
    // which includes the parsed environment variables
    const response = await fetch('/api/config')
    if (!response.ok) {
      throw new Error(`Failed to fetch config: ${response.status}`)
    }
    
    const runtimeConfig = await response.json()
    
    // Extract auth credentials from the runtime config
    // The server should include AUTH_USERNAME and AUTH_PASSWORD in the config
    const username = runtimeConfig.AUTH_USERNAME || 'dashboard'
    const password = runtimeConfig.AUTH_PASSWORD || 'dashboard123'
    
    return { username, password }
  } catch (error) {
    console.error('Failed to load auth credentials from config, using defaults:', error)
    
    // Fallback to default credentials if config loading fails
    return {
      username: 'dashboard',
      password: 'dashboard123'
    }
  }
}

/**
 * Create HTTP Basic Auth header value.
 * 
 * @param username - Username for authentication
 * @param password - Password for authentication
 * @returns Base64 encoded auth header value
 */
export function createBasicAuthHeader(username: string, password: string): string {
  const credentials = `${username}:${password}`
  const encoded = btoa(credentials)
  return `Basic ${encoded}`
}

/**
 * Get complete Authorization header for API requests.
 * Prioritizes JWT token if available, falls back to Basic Auth.
 * 
 * @returns Promise resolving to Authorization header object
 */
/**
 * Decode a JWT payload without verifying the signature.
 * Returns null if the token is malformed.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

/**
 * Returns true if the JWT token is expired (or malformed).
 */
function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token)
  if (!payload || typeof payload.exp !== 'number') return true
  // Add a 10-second buffer to catch tokens about to expire
  return payload.exp * 1000 < Date.now() + 10_000
}

export async function getAuthHeader(): Promise<Record<string, string>> {
  const jwtToken = localStorage.getItem('auth_token')
  if (!jwtToken) return {}

  // Proactively redirect on expired token before the request goes out
  if (isTokenExpired(jwtToken)) {
    handleUnauthorized()
    return {}
  }

  return { Authorization: `Bearer ${jwtToken}` }
}

/**
 * Check if user is authenticated with a non-expired token.
 */
export function isAuthenticated(): boolean {
  const token = localStorage.getItem('auth_token')
  if (!token) return false
  return !isTokenExpired(token)
}

/**
 * Clear authentication state (logout).
 */
export function logout(): void {
  localStorage.removeItem('auth_token')
}

/**
 * Handle 401 Unauthorized responses by redirecting to login.
 */
export function handleUnauthorized(): void {
  logout()
  if (!window.location.pathname.includes('/login')) {
    window.location.href = '/login'
  }
} 