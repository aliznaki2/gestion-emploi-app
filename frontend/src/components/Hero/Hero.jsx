import './Hero.css'

export default function Hero() {
  const scrollTo = (e, target) => {
    e.preventDefault()
    document.querySelector(target)?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <section className="hero" id="hero" aria-label="Section d'accueil ISTA NTIC 2">

      {/* ── Full-bleed photo ── */}
      <div className="hero__photo-wrap" aria-hidden="true">
        <img
          src="/hero-bg.jpg"
          alt="Campus ISTA NTIC Casablanca Nouvelles Technologies OFPPT"
          className="hero__photo"
        />
        <div className="hero__overlay"></div>
      </div>

      {/* ── Content ── */}
      <div className="container hero__inner">
        <div className="hero__content">

          {/* Location breadcrumb */}
          <div className="hero__breadcrumb" aria-label="Localisation">
            <img src="/ofppt.png" alt="OFPPT" className="hero__ofppt-logo" />
            <span className="hero__breadcrumb-sep" aria-hidden="true">·</span>
            <span>OFPPT</span>
            <span className="hero__breadcrumb-sep" aria-hidden="true">·</span>
            <span>Casablanca</span>
            <span className="hero__breadcrumb-sep" aria-hidden="true">·</span>
            <span>Sidi Maârouf</span>
          </div>

          {/* Title */}
          <h1 className="hero__title">
            Bienvenue à<br />
            <span className="hero__title-highlight">ISTA NTIC 2</span><br />
            <span className="hero__title-sub">Sidi Maârouf</span>
          </h1>

          {/* Description */}
          <p className="hero__desc">
            Institut Spécialisé de Technologie Appliquée — Découvrez votre établissement, 
            ses formations et les informations utiles à la vie des stagiaires.
          </p>

          {/* Buttons */}
          <div className="hero__actions">
            <a
              href="#formations"
              id="btn-formations"
              className="hero__btn hero__btn--primary"
              onClick={(e) => scrollTo(e, '#formations')}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
                <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/>
                <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/>
              </svg>
              Découvrir les formations
            </a>
            <a
              href="#about"
              id="btn-infos"
              className="hero__btn hero__btn--secondary"
              onClick={(e) => scrollTo(e, '#about')}
            >
              Consulter les informations
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </a>
          </div>

          {/* Info chips */}
          <div className="hero__chips" aria-label="Informations clés">
            <div className="hero__chip">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
                <circle cx="12" cy="10" r="3"/>
              </svg>
              1029, Route de Bouskoura, Sidi Maârouf, Casablanca
            </div>
            <div className="hero__chip">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/>
                <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/>
              </svg>
              Filières spécialisées NTIC & Gestion
            </div>
            <div className="hero__chip">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              Niveau Technicien Spécialisé (Bac +2)
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
