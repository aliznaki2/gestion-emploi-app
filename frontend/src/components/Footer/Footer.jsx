import {
  APP_NAME,
  AUTHORITY,
  NETWORK_NAME,
} from '../../config/branding'
import './Footer.css'

const YEAR = new Date().getFullYear()

export default function Footer({ onNavigateToLogin, onSubscribe }) {
  const handleNav = (e, target) => {
    e.preventDefault()
    document.querySelector(target)?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSubscribe = (e) => {
    e.preventDefault()
    if (onSubscribe) onSubscribe()
  }

  return (
    <footer className="footer" id="footer" aria-label="Pied de page">
      <div className="container footer__inner">

        {/* Brand column */}
        <div className="footer__brand">
          <div className="footer__logo-wrap">
            <img src="/ofppt.png" alt="Logo OFPPT" className="footer__ofppt-img" />
            <div className="footer__brand-text">
              <span className="footer__brand-name">{APP_NAME}</span>
              <span className="footer__brand-sub">{NETWORK_NAME} · {AUTHORITY.short}</span>
            </div>
          </div>
          <p className="footer__brand-desc">
            La plateforme de gestion des emplois du temps du <strong>{NETWORK_NAME}</strong>.
            Planification, génération automatique et publication des plannings pour chaque
            institut de l'<strong>{AUTHORITY.short}</strong>.
          </p>

          <div className="footer__workspace-badge">
            <span className="footer__workspace-dot" aria-hidden="true"></span>
            Plateforme du <strong>{NETWORK_NAME}</strong>
          </div>
        </div>

        {/* Navigation links */}
        <div className="footer__col">
          <h3 className="footer__col-title">Navigation</h3>
          <ul className="footer__links">
            <li><a href="#hero" className="footer__link" onClick={(e) => handleNav(e, '#hero')}>Accueil</a></li>
            <li><a href="#about" className="footer__link" onClick={(e) => handleNav(e, '#about')}>La plateforme</a></li>
            <li>
              <a href="#abonnement" className="footer__link" onClick={handleSubscribe}>
                Abonnement
              </a>
            </li>
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

        {/* Plateforme */}
        <div className="footer__col">
          <h3 className="footer__col-title">Plateforme</h3>
          <ul className="footer__links">
            <li><span className="footer__text-link">Emploi du temps</span></li>
            <li><span className="footer__text-link">Groupes & Sections</span></li>
            <li><span className="footer__text-link">Formateurs & Affectations</span></li>
            <li><span className="footer__text-link">Salles & Modules</span></li>
            <li><span className="footer__text-link">Espace formateur</span></li>
          </ul>
        </div>

        {/* Réseau */}
        <div className="footer__col">
          <h3 className="footer__col-title">Le réseau</h3>
          <ul className="footer__links">
            <li><span className="footer__text-link">Un espace par institut</span></li>
            <li><span className="footer__text-link">Abonnement en ligne</span></li>
            <li><span className="footer__text-link">Accompagnement & support</span></li>
            <li className="footer__network-empty">
              <span className="footer__network-empty-icon" aria-hidden="true">+</span>
              <div className="footer__network-empty-text">
                <span className="footer__network-empty-title">Rejoindre la plateforme</span>
                <span className="footer__network-empty-desc">Les instituts s'abonnent et activent leur espace de travail.</span>
              </div>
            </li>
            <li>
              <button type="button" className="footer__network-subscribe" onClick={onSubscribe}>
                S'abonner au réseau
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </li>
          </ul>
        </div>

        {/* Contact */}
        <div className="footer__col">
          <h3 className="footer__col-title">Contact & assistance</h3>
          <ul className="footer__links footer__links--contact">
            <li className="footer__contact-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M3 21h18" />
                <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
                <path d="M9 7h1M14 7h1M9 11h1M14 11h1M9 15h1M14 15h1" />
              </svg>
              <span>{NETWORK_NAME} · {AUTHORITY.short}</span>
            </li>
            <li className="footer__contact-item">
            </li>
            <li className="footer__contact-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
              <button type="button" className="footer__contact-button" onClick={onSubscribe}>
                Demander un abonnement
              </button>
            </li>
            <li className="footer__contact-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              <a
                href="#about"
                className="footer__contact-link"
                onClick={(e) => handleNav(e, '#about')}
              >
                Découvrir la plateforme
              </a>
            </li>
          </ul>
        </div>

      </div>

      {/* Bottom Bar */}
      <div className="footer__bottom">
        <div className="container footer__bottom-inner">
          <p className="footer__copyright">
            © {YEAR} <strong>{APP_NAME}</strong> · {NETWORK_NAME} · Établissement public de formation professionnelle <strong>{AUTHORITY.short}</strong>.
          </p>
          <div className="footer__bottom-links">
            <span className="footer__tag-badge">Plateforme de gestion des emplois du temps</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
