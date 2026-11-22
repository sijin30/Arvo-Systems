// Thin fetch wrapper. Every error from the server arrives as { error: { code, message } }.
const TOKEN_KEY = 'frontdesk.token'
const KIND_KEY = 'frontdesk.kind' // 'agent' (support staff) or 'customer'
let token = null
let onUnauthorized = () => {}

export function loadToken() {
  try {
    token = localStorage.getItem(TOKEN_KEY)
  } catch {
    token = null
  }
  return token
}

export function loadKind() {
  try {
    return localStorage.getItem(KIND_KEY)
  } catch {
    return null
  }
}

export function setToken(value, kind = null) {
  token = value
  try {
    if (value) {
      localStorage.setItem(TOKEN_KEY, value)
      if (kind) localStorage.setItem(KIND_KEY, kind)
    } else {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(KIND_KEY)
    }
  } catch {
    /* storage unavailable: the session simply will not survive a reload */
  }
}

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

export class ApiError extends Error {
  constructor(status, body) {
    const err = body?.error
    super(err?.message || `Request failed (${status})`)
    this.status = status
    this.code = err?.code || 'error'
    this.extra = err || {}
  }
}

async function send(path, { method = 'GET', body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, { error: { code: 'network', message: 'Cannot reach the server. Check your connection.' } })
  }
  if (res.status === 401 && token && !path.startsWith('/auth/login')) onUnauthorized()
  return res
}

export async function api(path, options) {
  const res = await send(path, options)
  if (res.status === 204) return null
  let data = null
  try {
    data = await res.json()
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

export async function download(path, filename) {
  const res = await send(path)
  if (!res.ok) throw new ApiError(res.status, null)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
