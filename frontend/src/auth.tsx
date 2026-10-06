import { createContext, useContext, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BriefcaseBusiness, WifiOff } from 'lucide-react'
import { api, ApiError, NetworkError } from './api'
import { accessKey, authKey, clearPrivateQueries, type AccessFailure } from './queryClient'

const AuthContext = createContext({ tokenRequired: false, logout: () => {}, loggingOut: false })
export const useAuth = () => useContext(AuthContext)

export function AuthGate({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const [token, setToken] = useState('')
  const [retrying, setRetrying] = useState(false)
  const failure = useQuery<AccessFailure>({ queryKey: accessKey, queryFn: () => null, initialData: null, enabled: false })
  const auth = useQuery({ queryKey: authKey, queryFn: api.getAuthStatus, retry: false, refetchInterval: failure.data ? false : 30000 })
  const reconnect = async () => {
    setRetrying(true)
    try {
      const status = await client.fetchQuery({ queryKey: authKey, queryFn: api.getAuthStatus, staleTime: 0, retry: false })
      await clearPrivateQueries(client)
      client.setQueryData(authKey, status)
      client.setQueryData(accessKey, null)
    } catch { /* QueryCache keeps the connection error visible. */ }
    finally { setRetrying(false) }
  }
  const login = useMutation({ mutationFn: () => api.login(token), onSuccess: async () => { setToken(''); await reconnect() } })
  const logout = useMutation({ mutationFn: api.logout, onSuccess: async () => {
    client.setQueryData(accessKey, { kind: 'unauthorized', message: '' })
    client.setQueryData(authKey, { token_required: true, authenticated: false })
    await clearPrivateQueries(client)
    await client.invalidateQueries({ queryKey: authKey })
  } })
  const offline = failure.data?.kind === 'offline' || auth.error instanceof NetworkError
  const locked = failure.data?.kind === 'unauthorized' || failure.data?.kind === 'forbidden' || (auth.data?.token_required && !auth.data.authenticated)
  const loginError = login.error instanceof ApiError && login.error.status === 401 ? 'Erişim anahtarı yanlış.' : login.error?.message
  const message = loginError || (failure.data?.kind === 'forbidden' ? failure.data.message : '')
  if (offline) return <div className="access-screen"><section className="access-card"><div className="modal-icon"><WifiOff size={25} /></div><h1>Bilgisayarına ulaşılamıyor</h1><p>Bilgisayarına ulaşılamıyor. Bilgisayarın açık, backend çalışıyor ve Tailscale bağlı olmalı.</p><button className="button primary" disabled={retrying} onClick={() => void reconnect()}>{retrying ? 'Bağlanıyor…' : 'Tekrar dene'}</button></section></div>
  if (locked) return <div className="access-screen"><section className="access-card"><div className="modal-icon"><BriefcaseBusiness size={25} /></div><h1>Apply Agent'a bağlan</h1><p>Bilgisayarındaki .env dosyasındaki API_TOKEN değerini gir. Bu cihaz hatırlanır.</p><form onSubmit={event => { event.preventDefault(); if (!login.isPending) login.mutate() }}><label className="field-label" htmlFor="access-token">Erişim anahtarı</label><input id="access-token" type="password" autoComplete="current-password" autoFocus value={token} onChange={event => setToken(event.target.value)} required disabled={login.isPending} />{message && <p className="inline-error" role="alert">{message}</p>}<button className="button primary" disabled={!token.trim() || login.isPending || retrying}>{login.isPending || retrying ? 'Bağlanıyor…' : 'Bağlan'}</button></form></section></div>
  if (auth.isPending) return <div className="access-screen" role="status">Bağlantı kontrol ediliyor…</div>
  if (auth.isError) return <div className="access-screen"><section className="access-card"><h1>Bağlantı kontrol edilemedi</h1><p role="alert">{auth.error.message}</p><button className="button primary" onClick={() => void reconnect()} disabled={retrying}>Tekrar dene</button></section></div>
  return <AuthContext.Provider value={{ tokenRequired: Boolean(auth.data?.token_required), logout: () => logout.mutate(), loggingOut: logout.isPending }}>{children}{logout.error && <p className="inline-error" role="alert">{logout.error.message}</p>}</AuthContext.Provider>
}
