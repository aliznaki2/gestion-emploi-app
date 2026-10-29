import './Footer.css'

const YEAR = new Date().getFullYear()

export default function Footer({ onNavigateToLogin }) {
  const handleNav = (e, target) => {
    e.preventDefault()
    document.querySelector(target)?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <footer className="footer" id="footer" aria-label="Pied de page">
      <div className="container footer__inner">
        
        {/* Brand column */}
        <div className="footer__brand">
          <div className="footer__logo-wrap">
            <img src="/ofppt.png" alt="Logo OFPPT" className="footer__ofppt-img" />
            <div className="footer__brand-text">
              <span className="footer__brand-name">ISTA NTIC 2</span>
              <span className="footer__brand-sub">Sidi Maârouf · Casablanca</span>
            </div>
          </div>
          <p className="footer__brand-desc">
            Institut Spécialisé de Technologie Appliquée relevant de l'<strong>OFPPT</strong>, 
            dédié aux métiers du numérique, du développement digital, de l'infrastructure et de la gestion d'entreprise.
          </p>
        </div>

        {/* Navigation links */}
        <div className="footer__col">
          <h3 className="footer__col-title">Navigation</h3>
          <ul className="footer__links">
            <li><a href="#hero" className="footer__link" onClick={(e) => handleNav(e, '#hero')}>Accueil</a></li>
            <li><a href="#about" className="footer__link" onClick={(e) => handleNav(e, '#about')}>L'établissement</a></li>
            <li><a href="#formations" className="footer__link" onClick={(e) => handleNav(e, '#formations')}>Formations & Filières</a></li>
            <li><a href="#actualites" className="footer__link" onClick={(e) => handleNav(e, '#actualites')}>Actualités & Rentrée</a></li>
            <li>
              <a
                href="#login"
                className="footer__link"
                onClick={(e) => {
                  e.preventDefault()
                  if (onNavigateToLogin) onNavigateToLogin()
                }}
              >
                Espace Connexion
              </a>
            </li>
          </ul>
        </div>

        {/* Filières */}
        <div className="footer__col">
          <h3 className="footer__col-title">Filières (Bac+2)</h3>
          <ul className="footer__links">
            <li><span className="footer__text-link">Dév. Web Full Stack</span></li>
            <li><span className="footer__text-link">Applications Mobiles</span></li>
            <li><span className="footer__text-link">Systèmes & Réseaux</span></li>
            <li><span className="footer__text-link">Cybersécurité</span></li>
            <li><span className="footer__text-link">Gestion des Entreprises (GEOCF)</span></li>
          </ul>
        </div>

        {/* Coordonnées vérifiées */}
        <div className="footer__col">
          <h3 className="footer__col-title">Coordonnées Officielles</h3>
          <ul className="footer__links footer__links--contact">
            <li className="footer__contact-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              <span>1029, Route de Bouskoura, Sidi Maârouf, Casablanca</span>
            </li>
            <li className="footer__contact-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
              <a href="mailto:istanticsm@gmail.com" className="footer__contact-link">istanticsm@gmail.com</a>
            </li>
            <li className="footer__contact-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
              <a href="https://sites.google.com/view/ista-ntic-sm/accueil" target="_blank" rel="noopener noreferrer" className="footer__contact-link">
                sites.google.com/view/ista-ntic-sm
              </a>
            </li>
            <li className="footer__contact-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              <a href="https://www.ofppt.ma" target="_blank" rel="noopener noreferrer" className="footer__contact-link">
                Portail officiel OFPPT.ma
              </a>
            </li>
          </ul>
        </div>

      </div>

      {/* Bottom Bar */}
      <div className="footer__bottom">
        <div className="container footer__bottom-inner">
          <p className="footer__copyright">
            © {YEAR} <strong>ISTA NTIC 2 Sidi Maârouf — Casablanca</strong> · Établissement public de formation professionnelle <strong>OFPPT</strong>.
          </p>
          <div className="footer__bottom-links">
            <span className="footer__tag-badge">OFPPT · NTIC Casablanca</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
