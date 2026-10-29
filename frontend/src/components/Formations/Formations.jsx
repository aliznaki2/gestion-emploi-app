import { useState } from 'react'
import './Formations.css'

const FORMATIONS = [
  {
    id: 'dev-fullstack',
    category: 'digital',
    badge: 'Digital & Informatique',
    badgeClass: 'badge-blue',
    title: 'Développement Digital — Option Web Full Stack',
    niveau: 'Technicien Spécialisé (Bac+2)',
    duree: '2 ans (Théorie & Stage)',
    description: 'Formation dédiée à la conception et au développement d\'applications web complètes (Front-end, Back-end, bases de données relationnelles et NoSQL, APIs RESTful et architectures Cloud).',
    competences: ['React / JavaScript', 'Node.js / PHP / Python', 'Bases de données SQL & NoSQL', 'DevOps & Git', 'Architecture MVC & REST'],
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    ),
  },
  {
    id: 'dev-mobile',
    category: 'digital',
    badge: 'Digital & Mobile',
    badgeClass: 'badge-blue',
    title: 'Développement Digital — Option Applications Mobiles',
    niveau: 'Technicien Spécialisé (Bac+2)',
    duree: '2 ans (Théorie & Stage)',
    description: 'Spécialisation dans le développement d\'applications mobiles performantes, interactives et intuitives pour smartphones et tablettes sous iOS et Android.',
    competences: ['Flutter / React Native', 'Android / iOS Natif', 'UI/UX Mobile Design', 'Intégration d\'APIs', 'Tests & Déploiement Stores'],
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
        <line x1="12" y1="18" x2="12.01" y2="18" />
      </svg>
    ),
  },
  {
    id: 'infra-reseaux',
    category: 'infra',
    badge: 'Infrastructure & Systèmes',
    badgeClass: 'badge-purple',
    title: 'Infrastructure Digitale — Option Systèmes & Réseaux',
    niveau: 'Technicien Spécialisé (Bac+2)',
    duree: '2 ans (Théorie & Stage)',
    description: 'Mise en place, administration et maintien en condition opérationnelle des parcs informatiques, serveurs d\'entreprise (Linux / Windows) et infrastructures réseau interconnectées.',
    competences: ['Réseaux TCP/IP & Routage', 'Administration Windows/Linux Server', 'Virtualisation (VMware/KVM)', 'Services Cloud', 'Maintenance & Support IT'],
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
        <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
        <line x1="6" y1="6" x2="6.01" y2="6" />
        <line x1="6" y1="18" x2="6.01" y2="18" />
      </svg>
    ),
  },
  {
    id: 'infra-cyber',
    category: 'infra',
    badge: 'Cybersécurité',
    badgeClass: 'badge-purple',
    title: 'Infrastructure Digitale — Option Cybersécurité',
    niveau: 'Technicien Spécialisé (Bac+2)',
    duree: '2 ans (Théorie & Stage)',
    description: 'Protection des systèmes d\'information contre les cybermenaces, sécurisation des flux de données, surveillance des incidents de sécurité et conformité réglementaire.',
    competences: ['Sécurité Réseaux & Firewalling', 'Audit & Détection des Vulnérabilités', 'Cryptographie & Protocoles Sécurisés', 'Gestion des Incidents', 'Sensibilisation & Bonnes Pratiques'],
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
    ),
  },
  {
    id: 'geocf',
    category: 'gestion',
    badge: 'Gestion & Finance',
    badgeClass: 'badge-emerald',
    title: 'Gestion des Entreprises — Comptabilité & Finance (GEOCF)',
    niveau: 'Technicien Spécialisé (Bac+2)',
    duree: '2 ans (Théorie & Stage)',
    description: 'Maîtrise des techniques de comptabilité générale et analytique, gestion financière, fiscalité des entreprises, contrôle de gestion et progiciels de gestion intégrés (PGI/ERP).',
    competences: ['Comptabilité Générale & Analytique', 'Gestion Financière & Trésorerie', 'Fiscalité Marocaine', 'Logiciels PGI / ERP', 'Contrôle Budgétaire'],
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <line x1="12" y1="1" x2="12" y2="23" />
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    ),
  },
]

export default function Formations() {
  const [activeFilter, setActiveFilter] = useState('all')

  const filtered = activeFilter === 'all'
    ? FORMATIONS
    : FORMATIONS.filter((item) => item.category === activeFilter)

  return (
    <section className="formations-section" id="formations" aria-label="Formations dispensées à ISTA NTIC 2">
      <div className="container">
        
        {/* Section Header */}
        <div className="section-header text-center">
          <div className="section-badge mx-auto">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
              <path d="M6 12v5c3 3 9 3 12 0v-5" />
            </svg>
            Offre de Formation OFPPT
          </div>
          <h2 className="section-title">
            Filières dispensées à <span className="highlight-text">ISTA NTIC 2</span>
          </h2>
          <p className="section-subtitle">
            Formations certifiantes de niveau <strong>Technicien Spécialisé (Bac+2)</strong> axées sur l'employabilité directe, les compétences technologiques de pointe et la gestion moderne.
          </p>
        </div>

        {/* Filter buttons */}
        <div className="formations__filters" role="tablist" aria-label="Filtres de filières">
          <button
            className={`formations__filter-btn ${activeFilter === 'all' ? 'active' : ''}`}
            onClick={() => setActiveFilter('all')}
            type="button"
          >
            Toutes les filières ({FORMATIONS.length})
          </button>
          <button
            className={`formations__filter-btn ${activeFilter === 'digital' ? 'active' : ''}`}
            onClick={() => setActiveFilter('digital')}
            type="button"
          >
            Digital & Dév Web/Mobile
          </button>
          <button
            className={`formations__filter-btn ${activeFilter === 'infra' ? 'active' : ''}`}
            onClick={() => setActiveFilter('infra')}
            type="button"
          >
            Infrastructure & Réseaux
          </button>
          <button
            className={`formations__filter-btn ${activeFilter === 'gestion' ? 'active' : ''}`}
            onClick={() => setActiveFilter('gestion')}
            type="button"
          >
            Gestion & Finance (GEOCF)
          </button>
        </div>

        {/* Cards Grid */}
        <div className="formations__grid">
          {filtered.map((item) => (
            <div key={item.id} className="formation-card">
              <div className="formation-card__header">
                <div className="formation-card__icon" aria-hidden="true">
                  {item.icon}
                </div>
                <span className={`formation-card__badge ${item.badgeClass}`}>
                  {item.badge}
                </span>
              </div>

              <h3 className="formation-card__title">{item.title}</h3>
              <p className="formation-card__desc">{item.description}</p>

              <div className="formation-card__meta">
                <div className="formation-card__meta-item">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  <span>{item.niveau}</span>
                </div>
                <div className="formation-card__meta-item">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  <span>{item.duree}</span>
                </div>
              </div>

              <div className="formation-card__skills">
                <p className="formation-card__skills-title">Compétences clés :</p>
                <div className="formation-card__tags">
                  {item.competences.map((tag) => (
                    <span key={tag} className="formation-card__tag">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="formation-card__footer">
                <span className="formation-card__ofppt-tag">
                  <img src="/ofppt.png" alt="OFPPT" width="16" height="16" />
                  Programme officiel OFPPT
                </span>
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  )
}
