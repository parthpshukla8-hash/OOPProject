import { Button, Field, Input } from '@fluentui/react-components'
import { Eye20Regular, EyeOff20Regular } from '@fluentui/react-icons'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ApiError } from '../api/api-client'
import { ErrorNotice } from '../components/ErrorNotice'
import { useAuth } from '../features/auth/auth-context'
import styles from './ChangePasswordPage.module.css'

export function ChangePasswordPage() {
  const { changePassword } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ oldPassword: '', newPassword: '', confirmPassword: '' })
  const [error, setError] = useState<ApiError | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [showOld, setShowOld] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }))

  const validate = () => {
    if (!form.oldPassword) return 'Current password is required'
    if (!form.newPassword) return 'New password is required'
    if (form.newPassword !== form.confirmPassword) return 'Passwords do not match'
    if (form.newPassword.length < 8) return 'Password must be at least 8 characters'
    return null
  }

  const submit = async () => {
    const validationError = validate()
    if (validationError) { setError({ status: 400, code: 'validation', message: validationError, extra: {} } as ApiError); return }

    setIsBusy(true)
    setError(null)
    try {
      await changePassword(form.oldPassword, form.newPassword)
      navigate('/login', { replace: true })
    } catch (failure) {
      setError(failure as ApiError)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <main className={styles['change-password-page']}>
      <div className={styles['change-password-page__panel']}>
        <h1 className={styles['change-password-page__brand']}>I-ITSM</h1>
        <p className={styles['change-password-page__lead']}>Update your password. You will need to sign in again afterwards.</p>
        <form className={styles['change-password-page__form']} onSubmit={(event) => { event.preventDefault(); submit() }}>
          <Field label="Current password">
            <Input
              type={showOld ? 'text' : 'password'}
              value={form.oldPassword}
              autoComplete="current-password"
              onChange={(_, d) => set({ oldPassword: d.value })}
              contentAfter={
                <Button
                  type="button"
                  size="small"
                  appearance="transparent"
                  icon={showOld ? <EyeOff20Regular /> : <Eye20Regular />}
                  aria-label={showOld ? 'Hide password' : 'Show password'}
                  aria-pressed={showOld}
                  onClick={() => setShowOld((v) => !v)}
                />
              }
            />
          </Field>
          <Field label="New password" hint="At least 8 characters, not a common password.">
            <Input
              type={showNew ? 'text' : 'password'}
              value={form.newPassword}
              autoComplete="new-password"
              onChange={(_, d) => set({ newPassword: d.value })}
              contentAfter={
                <Button
                  type="button"
                  size="small"
                  appearance="transparent"
                  icon={showNew ? <EyeOff20Regular /> : <Eye20Regular />}
                  aria-label={showNew ? 'Hide password' : 'Show password'}
                  aria-pressed={showNew}
                  onClick={() => setShowNew((v) => !v)}
                />
              }
            />
          </Field>
          <Field label="Confirm new password">
            <Input
              type={showConfirm ? 'text' : 'password'}
              value={form.confirmPassword}
              autoComplete="new-password"
              onChange={(_, d) => set({ confirmPassword: d.value })}
              contentAfter={
                <Button
                  type="button"
                  size="small"
                  appearance="transparent"
                  icon={showConfirm ? <EyeOff20Regular /> : <Eye20Regular />}
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                  aria-pressed={showConfirm}
                  onClick={() => setShowConfirm((v) => !v)}
                />
              }
            />
          </Field>
          {error && <ErrorNotice message={error.message} />}
          <Button type="submit" appearance="primary" disabled={isBusy || !form.oldPassword || !form.newPassword || !form.confirmPassword}>
            {isBusy ? 'Changing...' : 'Change password'}
          </Button>
        </form>
        <Button appearance="transparent" onClick={() => navigate(-1)}>Cancel</Button>
      </div>
    </main>
  )
}