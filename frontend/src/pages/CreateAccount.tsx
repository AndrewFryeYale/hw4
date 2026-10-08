import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registerUser } from '../api'
import { useAuth } from '../auth'

// Fields mirror the users table (first_name, last_name, email, password).
export default function CreateAccount() {
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
      const user = await registerUser({
        first_name: String(form.get('first_name')),
        last_name: String(form.get('last_name')),
        email: String(form.get('email')),
        password: String(form.get('password')),
      })
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
      <h1>Join the Pack</h1>
      <form className="auth-form" onSubmit={onSubmit}>
        <div className="row">
          <label>
            First name
            <input name="first_name" autoComplete="given-name" required />
          </label>
          <label>
            Last name
            <input name="last_name" autoComplete="family-name" required />
          </label>
        </div>
        <label>
          Email
          <input type="email" name="email" autoComplete="email" required />
        </label>
        <label>
          Password
          <input
            type="password"
            name="password"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Creating…' : 'Create Account'}
        </button>
        {error && <p className="error">{error}</p>}
      </form>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </section>
  )
}
