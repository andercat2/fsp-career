import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, tokenStore } from './api'

export type Me = {
  id: number
  email: string
  role: 'candidate' | 'employer' | 'admin'
  email_verified: boolean
  candidate?: { id: number; public_id: string; full_name: string | null; grade: string | null; specialization: string | null } | null
  company?: { id: number; name: string } | null
}

type AuthCtx = {
  user: Me | null
  loading: boolean
  signIn: (token: string) => Promise<Me>
  signOut: () => void
  refresh: () => Promise<void>
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(!!tokenStore.get())
  const qc = useQueryClient()

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) { setUser(null); setLoading(false); return }
    try {
      setUser(await api<Me>('/auth/me'))
    } catch {
      tokenStore.clear()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    const onUnauthorized = () => { setUser(null); qc.clear() }
    window.addEventListener('fsp:unauthorized', onUnauthorized)
    return () => window.removeEventListener('fsp:unauthorized', onUnauthorized)
  }, [qc])

  const signIn = useCallback(async (token: string) => {
    tokenStore.set(token)
    const me = await api<Me>('/auth/me')
    setUser(me)
    return me
  }, [])

  const signOut = useCallback(() => {
    tokenStore.clear()
    setUser(null)
    qc.clear()
  }, [qc])

  const value = useMemo(() => ({ user, loading, signIn, signOut, refresh }), [user, loading, signIn, signOut, refresh])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)

export const homeFor = (role?: string) =>
  role === 'employer' ? '/employer' : role === 'admin' ? '/admin' : '/candidate'
