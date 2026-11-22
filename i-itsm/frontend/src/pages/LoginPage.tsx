import { Button, Field, Input } from '@fluentui/react-components'
import { Eye20Regular, EyeOff20Regular } from '@fluentui/react-icons'
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
  const { login } = useAuth()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState<ApiError | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const submit = async (username = form.username, password = form.password) => {
    setIsBusy(true); setError(null)
    try { await login(username, password) } catch (failure) { setError(failure as ApiError) } finally { setIsBusy(false) }
  }

  return (
    <main className={styles['login-page']}>
      <div className={styles['login-page__panel']}>
        <h1 className={styles['login-page__brand']}>I-ITSM</h1>
        <p className={styles['login-page__lead']}>Something not working? Tell us once and follow it until it is fixed.</p>
        <form className={styles['login-page__form']} onSubmit={(event) => { event.preventDefault(); submit() }}>
          <Field label="Username"><Input value={form.username} autoComplete="username" onChange={(_, d) => setForm((current) => ({ ...current, username: d.value }))} /></Field>
          <Field label="Password">
            <Input
              type={showPassword ? 'text' : 'password'}
              value={form.password}
              autoComplete="current-password"
              onChange={(_, d) => setForm((current) => ({ ...current, password: d.value }))}
              contentAfter={
                <Button
                  type="button"
                  size="small"
                  appearance="transparent"
                  icon={showPassword ? <EyeOff20Regular /> : <Eye20Regular />}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((visible) => !visible)}
                />
              }
            />
          </Field>
          {error && <ErrorNotice message={error.message} />}
          <Button type="submit" appearance="primary" disabled={isBusy || !form.username || !form.password}>
            Sign in
          </Button>
        </form>
        <div className={styles['login-page__demo']}>
          <span>Demo accounts</span>
          {DEMO_ACCOUNTS.map((account) => (
            <Button key={account.username} size="small" appearance="subtle" onClick={() => submit(account.username, account.password)}>{account.label}</Button>
          ))}
        </div>
      </div>
    </main>
  )
}
