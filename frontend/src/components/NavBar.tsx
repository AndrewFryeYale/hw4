import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const tabs = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'nav-link active' : 'nav-link'

export default function NavBar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  function handleSignOut() {
    signOut()
    navigate('/')
  }

  return (
    <header className="navbar">
      <NavLink to="/" className="brand" aria-label="Campus Customs home">
        <span className="brand-mark" aria-hidden="true">CC</span>
        <span className="brand-text">
          <span className="brand-name">Campus Customs</span>
          <span className="brand-tag">57 Broadway · New Haven</span>
        </span>
      </NavLink>
      <nav className="nav-tabs">
        {tabs.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end={tab.end} className={linkClass}>
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <nav className="nav-account">
        {user ? (
          <>
            <span className="nav-greeting">Hi, {user.first_name ?? user.name}</span>
            <button type="button" className="nav-link nav-signout" onClick={handleSignOut}>
              Log Out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login" className={linkClass}>
              Log In
            </NavLink>
            <NavLink
              to="/create-account"
              className={({ isActive }) => `nav-link nav-cta${isActive ? ' active' : ''}`}
            >
              Create Account
            </NavLink>
          </>
        )}
      </nav>
    </header>
  )
}
