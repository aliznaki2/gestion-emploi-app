import { useState, useEffect } from 'react'
import './Navbar.css'

const NAV_LINKS = [
  { label: 'Accueil',           href: '#hero'        },
  { label: "L'établissement",   href: '#about'       },
  { label: 'Formations',        href: '#formations'  },
  { label: 'Actualités',        href: '#actualites'  },
]

export default function Navbar({ onNavigateToLogin }) {
  const [scrolled,  setScrolled]  = useState(false)
  const [menuOpen,  setMenuOpen]  = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const scrollTo = (e, target) => {
    e.preventDefault()
    setMenuOpen(false)
    document.querySelector(target)?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleConnexion = (e) => {
    e.preventDefault()
    setMenuOpen(false)
    if (onNavigateToLogin) {
      onNavigateToLogin()
    }
  }

  return (
    <header className={`navbar ${scrolled ? 'navbar--scrolled' : ''}`} id="navbar">
      <div className="container navbar__inner">

        {/* ── Logo ── */}
        <a href="#hero" className="navbar__logo" onClick={(e) => scrollTo(e, '#hero')}>
          <img src="/ofppt.png" alt="Logo OFPPT" className="navbar__ofppt-img" />
          <div className="navbar__logo-divider" aria-hidden="true"></div>
          <div className="navbar__logo-text">
            <span className="navbar__logo-name">ISTA NTIC 2</span>
            <span className="navbar__logo-sub">Sidi Maârouf · Casablanca</span>
          </div>
        </a>

        {/* ── Desktop Nav ── */}
        <nav className="navbar__links" aria-label="Navigation principale">
          {NAV_LINKS.map(({ label, href }) => (
            <a key={href} href={href} className="navbar__link" onClick={(e) => scrollTo(e, href)}>
              {label}
            </a>
          ))}
        </nav>

        {/* ── Bouton Connexion ── */}
        <div className="navbar__right">
          <button
            type="button"
            id="btn-connexion-nav"
            className="navbar__cta navbar__cta--connexion"
            onClick={handleConnexion}
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
              <polyline points="10 17 15 12 10 7" />
              <line x1="15" y1="12" x2="3" y2="12" />
            </svg>
            Connexion
          </button>
        </div>

        {/* ── Hamburger ── */}
        <button
          className={`navbar__hamburger ${menuOpen ? 'navbar__hamburger--open' : ''}`}
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label={menuOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
          aria-expanded={menuOpen}
          id="hamburger-btn"
        >
          <span></span><span></span><span></span>
        </button>
      </div>

      {/* ── Mobile Menu ── */}
      <div className={`navbar__mobile ${menuOpen ? 'navbar__mobile--open' : ''}`} id="mobile-menu" aria-hidden={!menuOpen}>
        <nav aria-label="Navigation mobile">
          {NAV_LINKS.map(({ label, href }) => (
            <a key={href} href={href} className="navbar__mobile-link" onClick={(e) => scrollTo(e, href)}>
              {label}
            </a>
          ))}
          <button
            type="button"
            className="navbar__mobile-connexion-btn"
            onClick={handleConnexion}
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
              <polyline points="10 17 15 12 10 7" />
              <line x1="15" y1="12" x2="3" y2="12" />
            </svg>
            Connexion
          </button>
        </nav>
        <div className="navbar__mobile-bottom">
          <img src="/ofppt.png" alt="OFPPT" className="navbar__ofppt-img" />
          <span className="navbar__mobile-brand">ISTA NTIC 2 · Casablanca</span>
        </div>
      </div>
    </header>
  )
}
