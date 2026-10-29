import './Actualites.css'

const ACTUALITES = [
  {
    id: 1,
    tag: 'Rentrée 2026-2027',
    tagColor: 'tag-red',
    date: 'Officiel ISTA NTIC 2',
    title: 'Dates de la rentrée de formation pour les stagiaires',
    content: (
      <>
        <p>Le calendrier officiel de rentrée fixé par la direction de l'ISTA NTIC 2 Sidi Maârouf :</p>
        <ul className="actualites__list">
          <li><strong>2ème année et 3ème année (S5) :</strong> Lundi 07 Septembre 2026</li>
          <li><strong>1ère année :</strong> Vendredi 11 Septembre 2026</li>
        </ul>
        <p className="actualites__note">Les stagiaires sont tenus de respecter scrupuleusement les horaires de reprise affichés.</p>
      </>
    ),
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
  {
    id: 2,
    tag: 'Horaires Officiels',
    tagColor: 'tag-blue',
    date: 'Règlement Intérieur',
    title: 'Grille des horaires d\'ouverture et des cours',
    content: (
      <>
        <p>Organisation des créneaux horaires d'apprentissage à l'ISTA NTIC 2 :</p>
        <ul className="actualites__list">
          <li>
            <strong>Lundi, Mardi, Mercredi, Jeudi et Samedi :</strong>
            <br />
            Matin : 08h00 – 13h00 | Après-midi : 13h30 – 18h30
          </li>
          <li>
            <strong>Vendredi :</strong>
            <br />
            Matin : 08h00 – 12h30 | Après-midi : 14h30 – 18h30
          </li>
        </ul>
      </>
    ),
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
  {
    id: 3,
    tag: 'Pédagogie & Groupes',
    tagColor: 'tag-amber',
    date: 'Affichage Stagiaires',
    title: 'Affectation des groupes et emplois du temps',
    content: (
      <>
        <p>
          Les listes de répartition des stagiaires par groupes (DEV101, DEV102, INFRA101, GEOCF101...) ainsi que les emplois du temps prévisionnels sont consultables en ligne et sur les tableaux d'affichage de l'institut.
        </p>
        <p className="actualites__note">
          Grâce à la solution GestEmploi, la génération des plannings est optimisée pour garantir le respect des volumes horaires et éviter les chevauchements de salles.
        </p>
      </>
    ),
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
]

export default function Actualites() {
  return (
    <section className="actualites-section" id="actualites" aria-label="Actualités et informations stagiaires">
      <div className="container">
        
        {/* Header */}
        <div className="section-header text-center">
          <div className="section-badge mx-auto">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
            Vie de l'établissement
          </div>
          <h2 className="section-title">
            Actualités & <span className="highlight-text">Informations Pratiques</span>
          </h2>
          <p className="section-subtitle">
            Informations officielles publiées par la direction de l'ISTA NTIC 2 Sidi Maârouf à l'attention des stagiaires et formateurs.
          </p>
        </div>

        {/* News Cards */}
        <div className="actualites__grid">
          {ACTUALITES.map((actu) => (
            <article key={actu.id} className="actu-card">
              <div className="actu-card__header">
                <div className="actu-card__icon" aria-hidden="true">
                  {actu.icon}
                </div>
                <div className="actu-card__meta">
                  <span className={`actu-card__tag ${actu.tagColor}`}>{actu.tag}</span>
                  <span className="actu-card__date">{actu.date}</span>
                </div>
              </div>

              <h3 className="actu-card__title">{actu.title}</h3>
              <div className="actu-card__body">{actu.content}</div>
            </article>
          ))}
        </div>

        {/* Contact info card banner */}
        <div className="actualites__contact-banner">
          <div className="actualites__contact-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
          </div>
          <div className="actualites__contact-text">
            <h4>Une question concernant votre scolarité ou les inscriptions ?</h4>
            <p>
              Contactez directement le secrétariat pédagogique de l'ISTA NTIC 2 Sidi Maârouf à l'adresse officielle :&nbsp;
              <a href="mailto:istanticsm@gmail.com" className="actualites__email-link">
                istanticsm@gmail.com
              </a>
            </p>
          </div>
          <a href="mailto:istanticsm@gmail.com" className="actualites__contact-btn">
            Contacter l'institut
          </a>
        </div>

      </div>
    </section>
  )
}
