import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'

export function useSettings() {
  const [settings, setSettings] = useState(null)

  useEffect(() => {
    api.get('/settings').then(setSettings).catch(() => {})
  }, [])

  const update = useCallback(async (values) => {
    setSettings((s) => (s ? { ...s, ...values } : s)) // optimistic
    try {
      setSettings(await api.put('/settings', { values }))
    } catch (e) {
      api.get('/settings').then(setSettings).catch(() => {})
      throw e
    }
  }, [])

  const reset = useCallback(async () => setSettings(await api.post('/settings/reset')), [])

  return { settings, update, reset }
}
