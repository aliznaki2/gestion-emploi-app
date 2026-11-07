import './EspaceFormateur.css'

/**
 * Espace réservé au profil « formateur ».
 *
 * L'interface formateur est volontairement séparée de l'espace administrateur :
 * ce profil ne doit disposer d'aucun accès aux données ni aux actions d'admin.
 * Cet écran est un point de départ à remplacer par la future interface dédiée.
 */
export default function EspaceFormateur({ onLogout }) {
  return (
    <div className="espace-formateur">
      <header className="espace-formateur__topbar">
        <div className="espace-formateur__brand">
          <h1>GestEmploi</h1>
          <span>ISTA NTIC 2 · Sidi Maârouf</span>
        </div>
        <span className="espace-formateur__role">Formateur</span>
      </header>

      <main className="espace-formateur__main">
        <section className="espace-formateur__card">
          <div className="espace-formateur__icon" aria-hidden="true">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </div>

          <h2>Espace formateur — accès restreint</h2>
          <p>
            L'interface formateur est en cours de développement et sera
            distincte de l'espace administrateur.
          </p>
          <p className="espace-formateur__note">
            Aucun privilège d'administration (emploi du temps, groupes,
            formateurs, salles, modules, filières, affectations) n'est accordé
            à ce profil.
          </p>

          <button
            type="button"
            className="espace-formateur__logout"
            onClick={onLogout}
          >
            Se déconnecter
          </button>
        </section>
      </main>

      <footer className="espace-formateur__footer">
        OFPPT — Institut Spécialisé de Technologie Appliquée NTIC 2
      </footer>
    </div>
  )
}
