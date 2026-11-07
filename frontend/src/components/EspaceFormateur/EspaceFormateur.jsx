import { useEffect, useMemo, useState } from 'react'
import './EspaceFormateur.css'

const API = 'http://localhost:3001/api'

const JOURS = [
  { id: 1, nom: 'Lundi' },
  { id: 2, nom: 'Mardi' },
  { id: 3, nom: 'Mercredi' },
  { id: 4, nom: 'Jeudi' },
  { id: 5, nom: 'Vendredi' },
  { id: 6, nom: 'Samedi' },
]

const NUMEROS_SEANCE = [1, 2, 3, 4]

const formatDate = (value) => {
  if (!value) return ''
  return new Date(value).toLocaleDateString('fr-MA', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

const apiFetch = async (url, opts = {}) => {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!response.ok) {
    let message = 'Erreur serveur'
    try {
      const body = await response.json()
      message = body.error || body.message || body.detail || message
    } catch {
      // Réponse non JSON : on garde le message générique.
    }
    throw new Error(message)
  }
  return response.json()
}

const horaire = (creneau) => {
  if (!creneau) return ''
  return `${creneau.heure_debut.slice(0, 5)}–${creneau.heure_fin.slice(0, 5)}`
}

/**
 * Espace du profil « formateur ».
 *
 * Deux pages :
 *  - Mes disponibilités : grille hebdomadaire des créneaux où le formateur est
 *    disponible ou non (les créneaux bloqués sont évités par le moteur).
 *  - Mon emploi du temps : son planning personnel pour la semaine choisie.
 */
export default function EspaceFormateur({ email = '', onLogout }) {
  const [activePage, setActivePage] = useState('disponibilites')

  const [professeurs, setProfesseurs] = useState([])
  const [creneaux, setCreneaux] = useState([])
  const [semaines, setSemaines] = useState([])
  const [profId, setProfId] = useState('')
  const [selectedSemaine, setSelectedSemaine] = useState(null)

  const [dispos, setDispos] = useState({})
  const [disposDirty, setDisposDirty] = useState(false)
  const [loadingDispos, setLoadingDispos] = useState(false)
  const [savingDispos, setSavingDispos] = useState(false)
  const [disposMessage, setDisposMessage] = useState('')
  const [disposError, setDisposError] = useState('')

  const [seances, setSeances] = useState([])
  const [loadingSeances, setLoadingSeances] = useState(false)
  const [seancesError, setSeancesError] = useState('')

  const [initialError, setInitialError] = useState('')

  // ── Chargement initial : profils, créneaux, semaines ─────────────────────
  useEffect(() => {
    let actif = true

    Promise.all([
      apiFetch(`${API}/professeurs`).catch(() => []),
      apiFetch(`${API}/creneaux`).catch(() => []),
      apiFetch(`${API}/semaines`).catch(() => []),
    ])
      .then(([profs, crs, sems]) => {
        if (!actif) return
        setProfesseurs(profs)
        setCreneaux(crs)
        setSemaines(sems)
        setSelectedSemaine(sems[0] || null)

        const emailNormalise = (email || '').trim().toLowerCase()
        let stocke = ''
        try {
          stocke = window.localStorage.getItem('gestemploi_prof_id') || ''
        } catch {
          stocke = ''
        }

        const parEmail = emailNormalise
          ? profs.find((p) => (p.email || '').trim().toLowerCase() === emailNormalise)
          : null
        const parStockage = profs.find((p) => String(p.id) === stocke)
        const premierActif = profs.find((p) => p.actif !== false)

        const choisi = parEmail || parStockage || premierActif || profs[0]
        setProfId(choisi ? String(choisi.id) : '')

        if (profs.length === 0) {
          setInitialError(
            "Aucun formateur n'est enregistré. Ajoutez d'abord un formateur dans l'espace administrateur.",
          )
        }
      })
      .catch((err) => {
        if (actif) setInitialError(err.message || 'Impossible de charger les données.')
      })

    return () => {
      actif = false
    }
  }, [email])

  const profSelectionne = useMemo(
    () => professeurs.find((p) => String(p.id) === String(profId)) || null,
    [professeurs, profId],
  )

  const emailNonLie = Boolean(
    email &&
      professeurs.length > 0 &&
      !professeurs.some(
        (p) => (p.email || '').trim().toLowerCase() === email.trim().toLowerCase(),
      ),
  )

  const choisirProf = (value) => {
    setProfId(value)
    try {
      window.localStorage.setItem('gestemploi_prof_id', value)
    } catch {
      // Stockage indisponible : le choix reste valable pour la session.
    }
  }

  // ── Disponibilités du formateur sélectionné ──────────────────────────────
  useEffect(() => {
    if (!profId) return
    let actif = true
    setLoadingDispos(true)
    setDisposError('')
    setDisposMessage('')

    apiFetch(`${API}/disponibilites?professeur=${profId}`)
      .then((liste) => {
        if (!actif) return
        const map = {}
        liste.forEach((d) => {
          map[d.creneau_id] = d.etat
        })
        setDispos(map)
        setDisposDirty(false)
      })
      .catch((err) => {
        if (actif) setDisposError(err.message || 'Impossible de charger les disponibilités.')
      })
      .finally(() => {
        if (actif) setLoadingDispos(false)
      })

    return () => {
      actif = false
    }
  }, [profId])

  // ── Emploi du temps de la semaine sélectionnée ───────────────────────────
  useEffect(() => {
    if (!selectedSemaine?.id) {
      setSeances([])
      return
    }
    let actif = true
    setLoadingSeances(true)
    setSeancesError('')

    apiFetch(`${API}/emploi-du-temps/${selectedSemaine.id}`)
      .then((liste) => {
        if (actif) setSeances(liste)
      })
      .catch((err) => {
        if (actif) {
          setSeances([])
          setSeancesError(err.message || "Impossible de charger l'emploi du temps.")
        }
      })
      .finally(() => {
        if (actif) setLoadingSeances(false)
      })

    return () => {
      actif = false
    }
  }, [selectedSemaine?.id])

  const creneauxParCellule = useMemo(() => {
    const map = {}
    creneaux.forEach((c) => {
      map[`${c.jour}-${c.numero_seance}`] = c
    })
    return map
  }, [creneaux])

  const mesSeances = useMemo(() => {
    if (!profId) return []
    return seances.filter((s) =>
      (s.professeurs || []).some((p) => String(p.prof_id) === String(profId)),
    )
  }, [seances, profId])

  const seancesParCellule = useMemo(() => {
    const map = {}
    mesSeances.forEach((s) => {
      const cle = `${s.jour}-${s.numero_seance}`
      if (!map[cle]) map[cle] = []
      map[cle].push(s)
    })
    return map
  }, [mesSeances])

  const statsSemaine = useMemo(() => {
    const groupes = new Set()
    const modules = new Set()
    let heures = 0
    mesSeances.forEach((s) => {
      heures += Number(s.duree_h) || 0
      modules.add(s.module_code)
      ;(s.groupes || []).forEach((g) => groupes.add(g.groupe_code))
    })
    return {
      seances: mesSeances.length,
      heures,
      groupes: groupes.size,
      modules: modules.size,
    }
  }, [mesSeances])

  const etatCreneau = (creneauId) => (
    dispos[creneauId] === 'bloque' ? 'bloque' : 'disponible'
  )

  const basculerCreneau = (creneauId) => {
    setDispos((prev) => {
      const courant = prev[creneauId] === 'bloque' ? 'bloque' : 'disponible'
      const suivant = courant === 'bloque' ? 'disponible' : 'bloque'
      return { ...prev, [creneauId]: suivant }
    })
    setDisposDirty(true)
    setDisposMessage('')
  }

  const toutDisponible = () => {
    setDispos({})
    setDisposDirty(true)
    setDisposMessage('')
  }

  const toutIndisponible = () => {
    const map = {}
    creneaux.forEach((c) => {
      map[c.id] = 'bloque'
    })
    setDispos(map)
    setDisposDirty(true)
    setDisposMessage('')
  }

  const enregistrerDispos = async () => {
    if (!profId) return
    setSavingDispos(true)
    setDisposError('')
    setDisposMessage('')
    try {
      const disponibilites = creneaux.map((c) => ({
        creneau_id: c.id,
        etat: etatCreneau(c.id),
      }))
      const enregistrees = await apiFetch(`${API}/disponibilites`, {
        method: 'PUT',
        body: JSON.stringify({
          professeur_id: Number(profId),
          disponibilites,
        }),
      })
      const map = {}
      ;(enregistrees || []).forEach((d) => {
        map[d.creneau_id] = d.etat
      })
      setDispos(map)
      setDisposDirty(false)
      setDisposMessage('Vos disponibilités ont été enregistrées.')
    } catch (err) {
      setDisposError(err.message || "Impossible d'enregistrer les disponibilités.")
    } finally {
      setSavingDispos(false)
    }
  }

  return (
    <div className="espace-formateur">
      <header className="espace-formateur__topbar">
        <div className="espace-formateur__brand">
          <h1>GestEmploi</h1>
          <span>ISTA NTIC 2 · Sidi Maârouf</span>
        </div>

        <div className="ef-topbar-right">
          {professeurs.length > 0 && (
            <label className="ef-profile">
              <span>Profil formateur</span>
              <select
                value={profId}
                onChange={(e) => choisirProf(e.target.value)}
              >
                {professeurs.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nom_complet}{p.matricule ? ` (${p.matricule})` : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
          <span className="espace-formateur__role">Formateur</span>
          <button
            type="button"
            className="espace-formateur__logout"
            onClick={onLogout}
          >
            Se déconnecter
          </button>
        </div>
      </header>

      <nav className="ef-tabs" aria-label="Espace formateur">
        <button
          type="button"
          className={`ef-tab ${activePage === 'disponibilites' ? 'active' : ''}`}
          onClick={() => setActivePage('disponibilites')}
        >
          Mes disponibilités
        </button>
        <button
          type="button"
          className={`ef-tab ${activePage === 'emploi' ? 'active' : ''}`}
          onClick={() => setActivePage('emploi')}
        >
          Mon emploi du temps
        </button>
      </nav>

      <main className="espace-formateur__main ef-main">
        {initialError && (
          <div className="ef-alert ef-alert--error">{initialError}</div>
        )}

        {emailNonLie && (
          <div className="ef-alert ef-alert--info">
            Le compte <strong>{email}</strong> n'est pas encore relié à une fiche
            formateur. Choisissez votre profil dans la liste ci-dessus.
          </div>
        )}

        {activePage === 'disponibilites' && (
          <section className="ef-card">
            <div className="ef-card-head">
              <div>
                <h2>Mes disponibilités</h2>
                <p>
                  Indiquez les créneaux où vous êtes disponible pour enseigner.
                  Les créneaux marqués <strong>Indisponible</strong> sont évités
                  lors de la génération de l'emploi du temps.
                </p>
              </div>
              {profSelectionne && (
                <span className="ef-prof-badge">{profSelectionne.nom_complet}</span>
              )}
            </div>

            <div className="ef-legend">
              <span><i className="ef-dot ef-dot--ok" /> Disponible</span>
              <span><i className="ef-dot ef-dot--off" /> Indisponible</span>
              <span className="ef-legend-hint">
                Cliquez sur un créneau pour changer son état.
              </span>
            </div>

            {disposError && <div className="ef-alert ef-alert--error">{disposError}</div>}
            {disposMessage && <div className="ef-alert ef-alert--success">{disposMessage}</div>}

            {loadingDispos ? (
              <div className="ef-empty">Chargement de vos disponibilités…</div>
            ) : (
              <div className="ef-grid-wrap">
                <table className="ef-grid">
                  <thead>
                    <tr>
                      <th className="ef-grid-corner">Séance</th>
                      {JOURS.map((jour) => (
                        <th key={jour.id}>{jour.nom}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {NUMEROS_SEANCE.map((numero) => (
                      <tr key={numero}>
                        <th className="ef-grid-time">
                          <span>Séance {numero}</span>
                          <small>
                            {horaire(creneauxParCellule[`1-${numero}`])}
                          </small>
                        </th>
                        {JOURS.map((jour) => {
                          const creneau = creneauxParCellule[`${jour.id}-${numero}`]
                          if (!creneau) {
                            return (
                              <td key={jour.id} className="ef-grid-cell">
                                <span className="ef-grid-na">—</span>
                              </td>
                            )
                          }
                          const etat = etatCreneau(creneau.id)
                          return (
                            <td key={jour.id} className="ef-grid-cell">
                              <button
                                type="button"
                                className={`ef-slot ef-slot--${etat}`}
                                onClick={() => basculerCreneau(creneau.id)}
                                title={`${jour.nom} ${horaire(creneau)} — ${etat === 'bloque' ? 'Indisponible' : 'Disponible'}`}
                              >
                                <span className="ef-slot-label">
                                  {etat === 'bloque' ? 'Indisponible' : 'Disponible'}
                                </span>
                                <span className="ef-slot-time">{horaire(creneau)}</span>
                              </button>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="ef-card-actions">
              <div className="ef-quick-actions">
                <button type="button" className="ef-btn ef-btn--ghost" onClick={toutDisponible}>
                  Tout disponible
                </button>
                <button type="button" className="ef-btn ef-btn--ghost" onClick={toutIndisponible}>
                  Tout indisponible
                </button>
              </div>
              <div className="ef-save-zone">
                {disposDirty && <span className="ef-dirty">Modifications non enregistrées</span>}
                <button
                  type="button"
                  className="ef-btn ef-btn--primary"
                  onClick={enregistrerDispos}
                  disabled={savingDispos || !profId || loadingDispos}
                >
                  {savingDispos ? 'Enregistrement…' : 'Enregistrer mes disponibilités'}
                </button>
              </div>
            </div>
          </section>
        )}

        {activePage === 'emploi' && (
          <section className="ef-card">
            <div className="ef-card-head">
              <div>
                <h2>Mon emploi du temps</h2>
                <p>
                  Vos séances pour la semaine sélectionnée, avec le groupe, le
                  module et la salle.
                </p>
              </div>
              <label className="ef-week">
                <span>Semaine</span>
                <select
                  value={selectedSemaine?.id || ''}
                  onChange={(e) => {
                    const semaine = semaines.find((s) => String(s.id) === e.target.value)
                    setSelectedSemaine(semaine || null)
                  }}
                >
                  {semaines.map((s) => (
                    <option key={s.id} value={s.id}>
                      Semaine {s.numero}
                      {s.date_debut ? ` (${formatDate(s.date_debut)} au ${formatDate(s.date_fin)})` : ''}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {profSelectionne && (
              <div className="ef-summary">
                <span className="ef-summary-prof">{profSelectionne.nom_complet}</span>
                <span><strong>{statsSemaine.seances}</strong> séance{statsSemaine.seances > 1 ? 's' : ''}</span>
                <span><strong>{statsSemaine.heures}</strong> h</span>
                <span><strong>{statsSemaine.groupes}</strong> groupe{statsSemaine.groupes > 1 ? 's' : ''}</span>
                <span><strong>{statsSemaine.modules}</strong> module{statsSemaine.modules > 1 ? 's' : ''}</span>
              </div>
            )}

            {seancesError && <div className="ef-alert ef-alert--error">{seancesError}</div>}

            {loadingSeances ? (
              <div className="ef-empty">Chargement de votre emploi du temps…</div>
            ) : mesSeances.length === 0 ? (
              <div className="ef-empty">
                <strong>Aucune séance cette semaine</strong>
                <span>
                  Votre emploi du temps apparaîtra ici dès que des séances vous
                  seront affectées.
                </span>
              </div>
            ) : (
              <div className="ef-grid-wrap">
                <table className="ef-grid ef-grid--planning">
                  <thead>
                    <tr>
                      <th className="ef-grid-corner">Séance</th>
                      {JOURS.map((jour) => (
                        <th key={jour.id}>{jour.nom}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {NUMEROS_SEANCE.map((numero) => (
                      <tr key={numero}>
                        <th className="ef-grid-time">
                          <span>Séance {numero}</span>
                          <small>{horaire(creneauxParCellule[`1-${numero}`])}</small>
                        </th>
                        {JOURS.map((jour) => {
                          const cellules = seancesParCellule[`${jour.id}-${numero}`] || []
                          return (
                            <td key={jour.id} className="ef-grid-cell ef-grid-cell--planning">
                              {cellules.length === 0 ? (
                                <span className="ef-grid-na">—</span>
                              ) : (
                                cellules.map((s) => (
                                  <div key={s.id} className={`ef-seance ef-seance--${s.statut}`}>
                                    <strong>{s.module_code}</strong>
                                    <span className="ef-seance-title">{s.module_intitule}</span>
                                    <span className="ef-seance-meta">
                                      {(s.groupes || []).map((g) => g.groupe_code).join(', ')}
                                    </span>
                                    <span className="ef-seance-meta">
                                      {s.salle_nom || 'Salle à définir'}
                                    </span>
                                    <span className={`ef-seance-status ef-seance-status--${s.statut}`}>
                                      {s.statut === 'valide' ? 'Validée' : 'Brouillon'}
                                    </span>
                                  </div>
                                ))
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selectedSemaine && (
              <div className="ef-card-actions">
                <span className="ef-period">
                  Semaine {selectedSemaine.numero}
                  {selectedSemaine.date_debut
                    ? ` · du ${formatDate(selectedSemaine.date_debut)} au ${formatDate(selectedSemaine.date_fin)}`
                    : ''}
                </span>
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="espace-formateur__footer">
        OFPPT — Institut Spécialisé de Technologie Appliquée NTIC 2
      </footer>
    </div>
  )
}
