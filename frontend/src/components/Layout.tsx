import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { checkHealth } from '../api/client'
import styles from './Layout.module.css'

export default function Layout() {
  const [online, setOnline] = useState<boolean | null>(null)

  useEffect(() => {
    checkHealth().then(setOnline)
    const interval = setInterval(() => checkHealth().then(setOnline), 30_000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 1L18 5V11C18 15.4 14.4 18.9 10 20.5C5.6 18.9 2 15.4 2 11V5L10 1Z"
              fill="none" stroke="#c8922a" strokeWidth="1.2"/>
            <circle cx="10" cy="10" r="3" fill="none" stroke="#c8922a" strokeWidth="1.2"/>
            <circle cx="10" cy="10" r="1" fill="#c8922a"/>
          </svg>
          <span className={styles.brandName}>EAGLE SCOUT</span>
          <span className={styles.brandSub}>/ LATAM INTELLIGENCE</span>
        </div>

        <nav className={styles.nav}>
          <NavLink to="/" end className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}>
            Overview
          </NavLink>
          <NavLink to="/search" className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}>
            Search
          </NavLink>
          <NavLink to="/opportunities" className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}>
            Opportunities
          </NavLink>
        </nav>

        <div className={styles.status}>
          <span className={styles.statusDot} data-online={online === true} />
          <span className={styles.statusLabel}>
            {online === null ? 'connecting' : online ? 'api online' : 'api offline'}
          </span>
        </div>
      </header>

      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
