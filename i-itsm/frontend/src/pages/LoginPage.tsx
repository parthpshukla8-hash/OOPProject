import { Button, Field, Input } from '@fluentui/react-components'
import { useState } from 'react'
import type { ApiError } from '../api/api-client'
import { ErrorNotice } from '../components/ErrorNotice'
import { useAuth } from '../features/auth/auth-context'
import styles from './LoginPage.module.css'

const DEMO_ACCOUNTS = [
  { label: 'Employee', username: 'e101', password: 'pass1234' },
  { label: 'Technician', username: 't101', password: 'tech1234' },
  { label: 'Administrator', username: 'admin', password: 'admin123' },
]

export function LoginPage() {
  const { login, register } = useAuth()
  const [isRegistering, setIsRegistering] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', firstName: '', lastName: '', email: '' })
  const [error, setError] = useState<ApiError | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }))

  const submit = async (username = form.username, password = form.password) => {
    setIsBusy(true); setError(null)
    try {
      if (isRegistering) await register({ ...form }); else await login(username, password)
    } catch (failure) { setError(failure as ApiError) } finally { setIsBusy(false) }
  }

  return (
    <main className={styles['login-page']}>
      <div className={styles['login-page__panel']}>
        <h1 className={styles['login-page__brand']}>I-ITSM</h1>
        <p className={styles['login-page__lead']}>Something not working? Tell us once and follow it until it is fixed.</p>
        <form className={styles['login-page__form']} onSubmit={(event) => { event.preventDefault(); submit() }}>
          {isRegistering && (
            <div className={styles['login-page__row']}>
              <Field label="First name"><Input value={form.firstName} onChange={(_, d) => set({ firstName: d.value })} /></Field>
              <Field label="Last name"><Input value={form.lastName} onChange={(_, d) => set({ lastName: d.value })} /></Field>
            </div>
          )}
          <Field label="Username"><Input value={form.username} autoComplete="username" onChange={(_, d) => set({ username: d.value })} /></Field>
          {isRegistering && <Field label="Work email"><Input type="email" value={form.email} onChange={(_, d) => set({ email: d.value })} /></Field>}
          <Field label="Password" hint={isRegistering ? 'At least 8 characters, not a common password.' : undefined}>
            <Input type="password" value={form.password} autoComplete={isRegistering ? 'new-password' : 'current-password'} onChange={(_, d) => set({ password: d.value })} />
          </Field>
          {error && <ErrorNotice message={error.message} />}
          <Button type="submit" appearance="primary" disabled={isBusy || !form.username || !form.password}>
            {isRegistering ? 'Create account' : 'Sign in'}
          </Button>
        </form>
        <Button appearance="transparent" onClick={() => { setIsRegistering(!isRegistering); setError(null) }}>
          {isRegistering ? 'I already have an account' : 'New here? Create an account'}
        </Button>
        {!isRegistering && (
          <div className={styles['login-page__demo']}>
            <span>Demo accounts</span>
            {DEMO_ACCOUNTS.map((account) => (
              <Button key={account.username} size="small" appearance="subtle" onClick={() => submit(account.username, account.password)}>{account.label}</Button>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
