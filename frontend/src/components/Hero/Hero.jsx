import { APP_NAME, APP_TAGLINE } from '../../config/branding'
import './Hero.css'

export default function Hero({ onNavigateToLogin, onSubscribe }) {
  const goToLogin = (e) => {
    e.preventDefault()
    if (onNavigateToLogin) onNavigateToLogin()
  }

  const openSubscription = (e) => {
    if (e) e.preventDefault()
    if (onSubscribe) onSubscribe()
  }

  return (
    <section className="hero" id="hero" aria-label={`${APP_NAME} — ${APP_TAGLINE}`}>

      {/* ── Full-bleed photo ── */}
      <div className="hero__photo-wrap" aria-hidden="true">
        <img
          src="/hero-bg.jpg"
          alt="Campus du réseau ISTA — OFPPT"
          className="hero__photo"
        />
        <div className="hero__overlay"></div>
      </div>

      {/* ── Content ── */}
      <div className="container hero__inner">
        <div className="hero__grid">

          <div className="hero__content">
            {/* Network breadcrumb */}
            <div className="hero__breadcrumb" aria-label="Plateforme">
              <img src="/ofppt.png" alt="OFPPT" className="hero__ofppt-logo" />
              <span className="hero__breadcrumb-sep" aria-hidden="true">·</span>
              <span>{APP_NAME}</span>
              <span className="hero__breadcrumb-sep" aria-hidden="true">·</span>
              <span>Réseau ISTA</span>
            </div>

            <span className="hero__eyebrow">Plateforme SaaS de planification</span>

            {/* Title */}
            <h1 className="hero__title">
              L'emploi du temps de votre institut,<br />
              <span className="hero__title-highlight">généré en quelques minutes.</span>
            </h1>

            {/* Description */}
            <p className="hero__desc">
              {APP_NAME} centralise les groupes, les formateurs et les salles de tous les
              instituts ISTA. Générez des plannings sans conflit, validez-les et partagez-les
              avec vos équipes — depuis un seul espace de travail.
            </p>

            {/* Buttons */}
            <div className="hero__actions">
              <a
                href="#login"
                id="btn-connexion-hero"
                className="hero__btn hero__btn--primary"
                onClick={goToLogin}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                  <polyline points="10 17 15 12 10 7" />
                  <line x1="15" y1="12" x2="3" y2="12" />
                </svg>
                Accéder à mon espace
              </a>
              <a
                href="#abonnement"
                id="btn-abonnement-hero"
                className="hero__btn hero__btn--secondary"
                onClick={openSubscription}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                S'abonner
              </a>
            </div>

            <a
              href="#about"
              className="hero__discover"
              onClick={(e) => {
                e.preventDefault()
                document.querySelector('#about')?.scrollIntoView({ behavior: 'smooth' })
              }}
            >
              Découvrir la plateforme
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="12" y1="5" x2="12" y2="19" />
                <polyline points="19 12 12 19 5 12" />
              </svg>
            </a>

            {/* Info chips */}
            <div className="hero__chips" aria-label="Atouts de la plateforme">
              <div className="hero__chip">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M3 21h18" />
                  <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
                </svg>
                Multi-instituts & multi-campus
              </div>
              <div className="hero__chip">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4" />
                  <circle cx="12" cy="12" r="4" />
                </svg>
                Génération automatique
              </div>
              <div className="hero__chip">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                Zéro conflit de salle
              </div>
            </div>
          </div>

          {/* ── Product preview ── */}
          <div className="hero__preview" aria-hidden="true">
            <div className="hero__preview-window">
              <div className="hero__preview-topbar">
                <span className="hero__preview-dots">
                  <i></i><i></i><i></i>
                </span>
                <span className="hero__preview-title">Emploi du temps · Semaine 12</span>
                <span className="hero__preview-badge">Généré</span>
              </div>

              <div className="hero__preview-toolbar">
                <span className="hero__preview-pill">Toutes les sections</span>
                <span className="hero__preview-pill hero__preview-pill--ghost">Lun → Sam</span>
              </div>

              <div className="hero__preview-grid">
                {[
                  ['DEV', '08:00', '#dbeafe'],
                  ['FS', '10:30', '#dcfce7'],
                  ['INFRA', '08:00', '#fef3c7'],
                  ['GEO', '13:30', '#ede9fe'],
                  ['DEV', '16:00', '#dbeafe'],
                  ['FS', '13:30', '#dcfce7'],
                  ['INFRA', '10:30', '#fef3c7'],
                  ['GEO', '08:00', '#ede9fe'],
                ].map(([label, time, color], index) => (
                  <div className="hero__preview-slot" key={`${label}-${index}`}>
                    <span className="hero__preview-chip" style={{ background: color }}>
                      {label}
                    </span>
                    <span className="hero__preview-time">{time}</span>
                  </div>
                ))}
              </div>

              <div className="hero__preview-stats">
                <div>
                  <strong>80</strong>
                  <span>séances planifiées</span>
                </div>
                <div>
                  <strong>0</strong>
                  <span>conflit détecté</span>
                </div>
                <div>
                  <strong>2,5 s</strong>
                  <span>temps de génération</span>
                </div>
              </div>
            </div>

            <div className="hero__preview-float">
              <span className="hero__preview-float-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
              <div>
                <strong>Semaine validée</strong>
                <span>Prête à être publiée</span>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* ── Scroll indicator ── */}
      <div className="hero__scroll" aria-hidden="true">
        <div className="hero__scroll-dot"></div>
      </div>
    </section>
  )
}
