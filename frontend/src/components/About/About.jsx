import './About.css'

const HIGHLIGHTS = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 00-3-3.87"/>
        <path d="M16 3.13a4 4 0 010 7.75"/>
      </svg>
    ),
    label: 'Formation professionnelle',
    desc: 'Technicien Spécialisé niveau Bac+2',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
      </svg>
    ),
    label: 'Technologies numériques',
    desc: 'Spécialisé en NTIC et Informatique',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
        <circle cx="12" cy="10" r="3"/>
      </svg>
    ),
    label: 'Sidi Maârouf, Casablanca',
    desc: '1029, Route de Bouskoura, 20190',
  },
]

export default function About() {
  return (
    <section className="about-section" id="about" aria-label="À propos de l'établissement">
      <div className="container about__inner">

        {/* ── Photo side ── */}
        <div className="about__visual">
          <div className="about__photo-frame">
            <img
              src="/ista-ntic-2.jpg"
              alt="Bâtiment de l'ISTA NTIC 2 Sidi Maârouf"
              className="about__photo"
            />
            {/* Floating badge */}
            <div className="about__badge" aria-label="Organisme de rattachement">
              <img src="/ofppt.png" alt="OFPPT" className="about__badge-logo" />
              <div>
                <span className="about__badge-title">OFPPT</span>
                <span className="about__badge-sub">Office de Formation Professionnelle<br/>et de la Promotion du Travail</span>
              </div>
            </div>
          </div>
          {/* Accent block */}
          <div className="about__accent-block" aria-hidden="true"></div>
        </div>

        {/* ── Text side ── */}
        <div className="about__content">
          <div className="section-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            L'établissement
          </div>

          <h2 className="section-title">
            ISTA NTIC 2 — <span className="about__title-accent">Institut Spécialisé de Technologie Appliquée</span>
          </h2>

          <p className="about__text">
            L'<strong>ISTA NTIC 2 Sidi Maârouf</strong> est un institut de formation professionnelle 
            relevant de l'<strong>OFPPT</strong> (Office de la Formation Professionnelle et de la 
            Promotion du Travail), situé dans le quartier <strong>Sidi Maârouf à Casablanca</strong>.
          </p>
          <p className="about__text">
            L'établissement dispense des formations de niveau <strong>Technicien Spécialisé (Bac+2)</strong>, 
            spécialisées dans les <strong>Nouvelles Technologies de l'Information et de la Communication (NTIC)</strong>. 
            Son objectif est de préparer les stagiaires aux métiers du numérique et de l'informatique 
            pour répondre aux besoins du marché de l'emploi marocain.
          </p>

          {/* Highlights */}
          <div className="about__highlights" aria-label="Points clés">
            {HIGHLIGHTS.map(({ icon, label, desc }) => (
              <div key={label} className="about__highlight">
                <div className="about__highlight-icon" aria-hidden="true">{icon}</div>
                <div>
                  <p className="about__highlight-label">{label}</p>
                  <p className="about__highlight-desc">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
