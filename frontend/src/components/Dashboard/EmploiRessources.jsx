import { Fragment, useMemo, useState } from 'react'

// ─── Utilitaires ──────────────────────────────────────────────────────────────
const DUREE_SEANCE_H = 2.5

/** Nombre de créneaux vides entre le premier et le dernier créneau occupé d'une journée. */
const compterTrous = (numeros) => {
  const n = [...new Set(numeros)].sort((a, b) => a - b)
  return n.length < 2 ? 0 : (n[n.length - 1] - n[0] + 1) - n.length
}

const cleSlot = (id, jour, seance) => `${id}_${jour}_${seance}`

const libelleSalle = (s) => s.salle_nom || (s.mode === 'distance' ? 'TEAM' : '—')

// ─── Tableau d'emploi du temps par formateur ou par salle ─────────────────────
/**
 * Affiche l'emploi du temps de la semaine pour chaque formateur (`mode="formateur"`)
 * ou chaque salle (`mode="salle"`), avec la même mise en page que l'emploi des groupes.
 *
 * Les trois emplois proviennent des mêmes séances : l'emploi des formateurs est
 * calculé en premier, ceux des stagiaires et des salles en sont dérivés.
 */
export function EmploiParRessource({
  mode,
  seances,
  professeurs,
  salles,
  jours,
  slots,
  formatGroupe = (c) => c,
  formatProf = (profs) => (profs || []).map((p) => p.prof_nom).join(' / '),
  onSelectSeance,
}) {
  const [recherche, setRecherche] = useState('')
  const [afficherVides, setAfficherVides] = useState(false)
  const estFormateur = mode === 'formateur'

  // Index des séances : ressource + jour + numéro de séance → séances
  const index = useMemo(() => {
    const map = {}
    for (const s of seances) {
      const ids = estFormateur
        ? (s.professeurs || []).map((p) => p.prof_id)
        : (s.salle_id ? [s.salle_id] : [])
      for (const id of ids) {
        const k = cleSlot(id, s.jour, s.numero_seance)
        ;(map[k] = map[k] || []).push(s)
      }
    }
    return map
  }, [seances, estFormateur])

  const lignes = useMemo(() => {
    const ressources = estFormateur
      ? professeurs.filter((p) => p.actif !== false).map((p) => ({ id: p.id, nom: p.nom_complet, plafond: p.heures_max_semaine }))
      : salles.filter((r) => r.actif !== false && !r.est_virtuelle).map((r) => ({ id: r.id, nom: r.nom, type: r.type_code }))

    return ressources
      .map((r) => {
        let nb = 0
        let trous = 0
        let conflits = 0
        const jours_actifs = new Set()
        for (const j of jours) {
          const numeros = []
          for (let n = 1; n <= 4; n++) {
            const l = index[cleSlot(r.id, j.id, n)]
            if (l) {
              nb += 1
              numeros.push(n)
              jours_actifs.add(j.id)
              if (l.length > 1) conflits += 1
            }
          }
          trous += compterTrous(numeros)
        }
        return { ...r, nb, trous, conflits, jours: jours_actifs.size }
      })
      .filter((r) => afficherVides || r.nb > 0)
      .filter((r) => !recherche || r.nom?.toLowerCase().includes(recherche.toLowerCase()))
      .sort((a, b) => (a.nom || '').localeCompare(b.nom || ''))
  }, [estFormateur, professeurs, salles, jours, index, afficherVides, recherche])

  const totalSeances = lignes.reduce((t, r) => t + r.nb, 0)
  const titreRessource = estFormateur ? 'Formateur' : 'Salle'
  const libellesLignes = estFormateur ? ['GROUPE', 'MODULE', 'SALLE'] : ['GROUPE', 'MODULE', 'FORMATEUR']

  const cellule = (r, slot, ligne) => {
    const liste = index[cleSlot(r.id, slot.jour, slot.seance)]
    if (!liste) return <td key={`${ligne}_${slot.jour}_${slot.seance}`} className="vide" />
    const s = liste[0]
    const conflit = liste.length > 1
    let contenu
    if (ligne === 0) {
      contenu = [...new Set(liste.flatMap((x) => (x.groupes || []).map((g) => formatGroupe(g.groupe_code))))].join(' / ')
    } else if (ligne === 1) {
      contenu = (
        <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
          {s.nature === 'examen' && <span className="efm-badge">EFM</span>}
          <span>{s.module_intitule || s.module_code}</span>
        </span>
      )
    } else {
      contenu = estFormateur ? libelleSalle(s) : formatProf(s.professeurs)
    }
    return (
      <td
        key={`${ligne}_${slot.jour}_${slot.seance}`}
        className={`${ligne === 1 ? 'module ' : ''}cell-clickable`}
        style={conflit ? { outline: '2px solid #dc2626', outlineOffset: -2 } : undefined}
        onClick={() => onSelectSeance && onSelectSeance(s)}
        title={
          `${s.module_intitule} (${s.module_code})` +
          ` | Groupes: ${(s.groupes || []).map((g) => g.groupe_code).join(', ') || '—'}` +
          ` | Formateur: ${(s.professeurs || []).map((p) => p.prof_nom).join(', ') || '—'}` +
          ` | Salle: ${libelleSalle(s)}` +
          (conflit ? ' | ⚠ CONFLIT : plusieurs séances sur ce créneau' : '')
        }
      >
        {contenu}
        {conflit && ' ⚠'}
      </td>
    )
  }

  return (
    <div>
      <div className="controls-bar" style={{ marginBottom: 10 }}>
        <input
          type="text"
          placeholder={estFormateur ? 'Filtrer un formateur…' : 'Filtrer une salle…'}
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          style={{ width: 220 }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={afficherVides} onChange={(e) => setAfficherVides(e.target.checked)} />
          Afficher aussi {estFormateur ? 'les formateurs' : 'les salles'} sans séance
        </label>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 13, color: '#64748b' }}>
          <strong>{lignes.length}</strong> {estFormateur ? 'formateur(s)' : 'salle(s)'} · <strong>{totalSeances}</strong> créneau(x) occupé(s)
        </span>
      </div>

      {lignes.length === 0 ? (
        <div className="empty-state">
          <h3>{estFormateur ? 'Aucun formateur planifié' : 'Aucune salle utilisée'} cette semaine</h3>
          <p>Générez l'emploi de la semaine ou cochez « Afficher aussi… » pour voir toutes les ressources.</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="ntic-table">
            <thead>
              <tr>
                <th rowSpan={3}>{titreRessource}</th>
                <th rowSpan={3}>Information</th>
                {jours.map((j) => <th key={j.id} colSpan={4}>{j.nom}</th>)}
                <th rowSpan={3}>{estFormateur ? 'Charge' : 'Occupation'}</th>
              </tr>
              <tr>
                {slots.map((s) => <th key={`n_${s.jour}_${s.seance}`}>SEANCE {s.seance}</th>)}
              </tr>
              <tr className="horaire">
                {slots.map((s) => <th key={`h_${s.jour}_${s.seance}`}>{s.horaire}</th>)}
              </tr>
            </thead>
            <tbody>
              {lignes.map((r) => {
                const heures = r.nb * DUREE_SEANCE_H
                const surcharge = estFormateur && r.plafond && heures > Number(r.plafond)
                return (
                  <Fragment key={r.id}>
                    <tr>
                      <td rowSpan={3} className="groupe">{r.nom}</td>
                      <td className="type">{libellesLignes[0]}</td>
                      {slots.map((s) => cellule(r, s, 0))}
                      <td rowSpan={3} className="effectif" style={surcharge || r.conflits ? { color: '#dc2626', fontWeight: 700 } : undefined}>
                        {estFormateur ? (
                          <>
                            {heures} h{r.plafond ? ` / ${Number(r.plafond)} h` : ''}
                            <br /><small>{r.jours} jour(s) · {r.trous} trou(s)</small>
                          </>
                        ) : (
                          <>
                            {r.nb} / {slots.length}
                            <br /><small>{Math.round((r.nb / slots.length) * 100)} %{r.type ? ` · ${r.type}` : ''}</small>
                          </>
                        )}
                        {r.conflits > 0 && <><br /><small>⚠ {r.conflits} conflit(s)</small></>}
                      </td>
                    </tr>
                    <tr>
                      <td className="type">{libellesLignes[1]}</td>
                      {slots.map((s) => cellule(r, s, 1))}
                    </tr>
                    <tr>
                      <td className="type">{libellesLignes[2]}</td>
                      {slots.map((s) => cellule(r, s, 2))}
                    </tr>
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Panneau « déroulé de la génération » ─────────────────────────────────────
const couleurStatut = (statut) =>
  ['OPTIMAL', 'FEASIBLE', 'DERIVE'].includes(statut) ? '#16a34a' : '#dc2626'

function Etape({ numero, titre, soustitre, statut, lignes }) {
  return (
    <div style={{ flex: '1 1 260px', background: '#fff', border: '1px solid #dbeafe', borderRadius: 8, padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{
          width: 24, height: 24, borderRadius: '50%', background: '#1a5fa8', color: '#fff',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700,
        }}>{numero}</span>
        <strong style={{ color: '#0f2d5e' }}>{titre}</strong>
        {statut && (
          <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 700, color: couleurStatut(statut) }}>
            {statut === 'DERIVE' ? 'DÉRIVÉ' : statut}
          </span>
        )}
      </div>
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}>{soustitre}</div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#334155', lineHeight: 1.6 }}>
        {lignes.map(([label, valeur]) => (
          <li key={label}>{label} : <strong>{valeur}</strong></li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Montre les trois étapes de la dernière génération : l'emploi des formateurs est
 * calculé d'abord, ceux des stagiaires et des salles sont dérivés.
 */
export function PipelineGeneration({ resume, numeroSemaine, onClose }) {
  const p3 = resume?.phase3
  if (!p3) return null
  const f = p3.emploi_formateurs || {}
  const g = p3.emploi_stagiaires || {}
  const s = p3.emploi_salles || {}
  const etapes = p3.etapes || {}
  const efm = p3.efm_hors_date || []
  const secondes = (ms) => (ms ? `${(ms / 1000).toFixed(1)} s` : '—')

  return (
    <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, padding: '12px 14px', margin: '12px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <strong style={{ color: '#1e40af' }}>
          Dernière génération{numeroSemaine ? ` — semaine ${numeroSemaine}` : ''} : formateurs → stagiaires → salles
        </strong>
        <span style={{ fontSize: 12, color: '#64748b' }}>
          {p3.seances_placees} séance(s) · {secondes(p3.temps_resolution_ms)}
        </span>
        <button className="btn btn-ghost" style={{ marginLeft: 'auto' }} onClick={onClose}>Masquer</button>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Etape
          numero="1" titre="Emploi des formateurs"
          soustitre={`Calculé en premier (${secondes(etapes.formateurs?.temps_ms)})`}
          statut={etapes.formateurs?.statut}
          lignes={[
            ['Formateurs planifiés', f.formateurs_planifies ?? '—'],
            ['Charge maximale', f.heures_max != null ? `${f.heures_max} h` : '—'],
            ['Créneaux vides entre séances', f.trous ?? '—'],
            ['Jours de présence (total)', f.jours_de_presence ?? '—'],
          ]}
        />
        <Etape
          numero="2" titre="Emploi des stagiaires"
          soustitre="Dérivé de l'emploi des formateurs, puis vérifié"
          statut={etapes.stagiaires?.statut}
          lignes={[
            ['Groupes planifiés', g.groupes_planifies ?? '—'],
            ['Charge par groupe', g.heures_min != null ? `${g.heures_min} – ${g.heures_max} h` : '—'],
            ['Créneaux vides entre séances', g.trous ?? '—'],
            ['Journées de 10 h', g.journees_10h ?? '—'],
            ['Conflits', g.conflits ?? 0],
          ]}
        />
        <Etape
          numero="3" titre="Emploi des salles"
          soustitre={`Dérivé des créneaux fixés (${secondes(etapes.salles?.temps_ms)})`}
          statut={etapes.salles?.statut}
          lignes={[
            ['Salles utilisées', s.salles_utilisees ?? '—'],
            ['Séances sans salle', s.seances_sans_salle ?? 0],
            ['Changements de salle d\'un formateur', f.changements_de_salle ?? '—'],
          ]}
        />
      </div>

      {efm.length > 0 && (
        <details style={{ marginTop: 10, fontSize: 13, color: '#92400e' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
            {efm.length} EFM n'ont pas pu être placés à leur date
          </summary>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {efm.slice(0, 20).map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}
