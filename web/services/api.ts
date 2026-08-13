import axios from 'axios'


function getApiBaseUrl(): string {
  const raw = localStorage.getItem('api_base_url') || ''
  let base = raw.trim() || '/api'
  if (base !== '/api' && !/^https?:\/\//i.test(base)) {
    const scheme = window.location.protocol === 'https:' ? 'https' : 'http'
    base = `${scheme}://${base}`
  }
  base = base.replace(/\/+$/, '')
  return base.endsWith('/api') ? base : `${base}/api`
}

const api = axios.create({ baseURL: getApiBaseUrl() })

api.interceptors.request.use((config: any) => {
  const token = localStorage.getItem('api_token') || ''
  const user = localStorage.getItem('api_user') || 'admin'
  const pass = localStorage.getItem('api_pass') || 'admin'
  config.baseURL = getApiBaseUrl()
  config.headers = {
    ...config.headers,
    ...(token && token !== 'change_me'
      ? { 'X-API-Token': token }
      : { Authorization: `Basic ${btoa(`${user}:${pass}`)}` }),
  }
  return config
})

export default api
