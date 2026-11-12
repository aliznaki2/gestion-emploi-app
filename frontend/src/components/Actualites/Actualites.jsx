import { APP_NAME, useInstitute } from '../../config/branding'
import './Actualites.css'

const buildActualites = (institute) => [
  {
    id: 1,
    tag: 'Rentrée 2026-2027',
    tagColor: 'tag-red',
    date: `Officiel · ${institute.name}`,
    title: 'Dates de la rentrée de formation pour les stagiaires',
    content: (
      <>
        <p>Le calendrier officiel de rentrée fixé par la direction de {institute.name} :</p>
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
        <p>Organisation des créneaux horaires d'apprentissage à {institute.name} :</p>
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
          Les listes de répartition des stagiaires par groupes ainsi que les emplois du temps
          prévisionnels sont consultables en ligne et sur les tableaux d'affichage de l'institut.
        </p>
        <p className="actualites__note">
          Grâce à la solution {APP_NAME}, la génération des plannings est optimisée pour garantir
          le respect des volumes horaires et éviter les chevauchements de salles.
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
  const [institute] = useInstitute()
  const actualites = buildActualites(institute)

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
            Vie du réseau
          </div>
          <h2 className="section-title">
            Actualités & <span className="highlight-text">Informations Pratiques</span>
          </h2>
          <p className="section-subtitle">
            Informations officielles publiées à l'attention des stagiaires et formateurs des
            instituts ISTA.
          </p>

          <div className="actualites__scope">
            <span className="actualites__scope-dot" aria-hidden="true"></span>
            Institut consulté&nbsp;: <strong>{institute.name}</strong>
            <span className="actualites__scope-city">· {institute.district}, {institute.city}</span>
          </div>
        </div>

        {/* News Cards */}
        <div className="actualites__grid">
          {actualites.map((actu) => (
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



      </div>
    </section>
  )
}
