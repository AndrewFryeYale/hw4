import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { loginUser } from '../api'
import { useAuth } from '../auth'

export default function Login() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    const form = new FormData(e.currentTarget)
    try {
      const user = await loginUser(
        String(form.get('email')),
        String(form.get('password')),
      )
      signIn(user)
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="section auth">
      <h1>Welcome Back</h1>
      <form className="auth-form" onSubmit={onSubmit}>
        <label>
          Email
          <input type="email" name="email" autoComplete="email" required />
        </label>
        <label>
          Password
          <input type="password" name="password" autoComplete="current-password" required />
        </label>
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Signing in…' : 'Log In'}
        </button>
        {error && <p className="error">{error}</p>}
      </form>
      <p className="muted">
        New here? <Link to="/create-account">Create an account</Link>
      </p>
    </section>
  )
}
