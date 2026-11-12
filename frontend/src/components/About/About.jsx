import { APP_NAME, NETWORK_NAME } from '../../config/branding'
import './About.css'

const HIGHLIGHTS = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M3 21h18" />
        <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
        <path d="M9 7h1M14 7h1M9 11h1M14 11h1M9 15h1M14 15h1" />
      </svg>
    ),
    label: 'Un espace par institut',
    desc: 'Chaque ISTA conserve ses groupes, ses salles et ses formateurs.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    ),
    label: 'Génération intelligente',
    desc: 'Le moteur CP-SAT place les séances sans conflit en quelques secondes.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
    label: 'Travail collaboratif',
    desc: 'Administration, formateurs et disponibilités réunis dans un seul flux.',
  },
]

const PLATFORM_POINTS = [
  { value: '01', label: 'Import des groupes, modules et formateurs' },
  { value: '02', label: 'Génération et arbitrage des contraintes' },
  { value: '03', label: 'Validation puis publication des plannings' },
]

export default function About({ onSubscribe }) {
  return (
    <section className="about-section" id="about" aria-label={`À propos de ${APP_NAME}`}>
      <div className="container about__inner">

        {/* ── Text side ── */}
        <div className="about__content">
          <div className="section-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            La plateforme
          </div>

          <h2 className="section-title">
            {APP_NAME} — <span className="about__title-accent">le pilotage des plannings à l'échelle du réseau ISTA</span>
          </h2>

          <p className="about__text">
            <strong>{APP_NAME}</strong> est la plateforme SaaS de gestion des emplois du temps
            du <strong>{NETWORK_NAME}</strong> (OFPPT). Elle réunit dans une même interface
            les groupes, les formateurs, les salles et les modules de chaque institut.
          </p>
          <p className="about__text">
            De l'affectation des enseignements à la publication des plannings, chaque
            établissement travaille dans <strong>son propre espace de travail</strong> tout en
            partageant les mêmes règles pédagogiques et les mêmes contraintes horaires.
          </p>

          {/* SaaS call to action */}
          <div className="about__cta">
            <div className="about__cta-text-block">
              <p className="about__cta-title">Une plateforme, tous les instituts</p>
              <p className="about__cta-desc">
                Chaque établissement dispose de son propre espace de travail, activé lors de
                son abonnement à {APP_NAME}.
              </p>
            </div>
            <div className="about__cta-actions">
              <button type="button" className="about__cta-primary" onClick={onSubscribe}>
                S'abonner
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
              <a href="#login" className="about__cta-secondary">Se connecter</a>
            </div>
          </div>

          {/* Highlights */}
          <div className="about__highlights" aria-label="Fonctionnalités clés">
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

          {/* Platform flow */}
          <div className="about__flow" aria-label="Cycle de planification">
            {PLATFORM_POINTS.map((point) => (
              <div key={point.value} className="about__flow-step">
                <span className="about__flow-number">{point.value}</span>
                <span className="about__flow-label">{point.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
