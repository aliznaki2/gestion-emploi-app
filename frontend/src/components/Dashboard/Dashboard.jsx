import React, { useState, useEffect, useCallback, useMemo, Fragment } from 'react'
import './Dashboard.css'

const API = 'http://localhost:3001/api'

// ─── Constants ────────────────────────────────────────────────────────────────
const JOURS = [
  { id: 1, nom: 'Lundi' },
  { id: 2, nom: 'Mardi' },
  { id: 3, nom: 'Mercredi' },
  { id: 4, nom: 'Jeudi' },
  { id: 5, nom: 'Vendredi' },
  { id: 6, nom: 'Samedi' },
]

// Slot horaires: Lundi-Jeudi & Samedi: 08h00-10h30, 10h30-13h00, 13h30-16h00, 16h00-18h30
// Vendredi: 08h00-10h30, 10h30-12h30, 14h30-16h30, 16h30-18h30
const getSlotHoraire = (jourId, seanceNum) => {
  if (jourId === 5) {
    if (seanceNum === 1) return '08h00-10h30'
    if (seanceNum === 2) return '10h30-12h30'
    if (seanceNum === 3) return '14h30-16h30'
    return '16h30-18h30'
  }
  if (seanceNum === 1) return '08h00-10h30'
  if (seanceNum === 2) return '10h30-13h00'
  if (seanceNum === 3) return '13h30-16h00'
  return '16h00-18h30'
}

// 24 slots sequence: (Jour 1 S1..S4, Jour 2 S1..S4, ..., Jour 6 S1..S4)
const ALL_24_SLOTS = []
for (const j of JOURS) {
  for (let s = 1; s <= 4; s++) {
    ALL_24_SLOTS.push({
      jour: j.id,
      jourNom: j.nom,
      seance: s,
      horaire: getSlotHoraire(j.id, s)
    })
  }
}

// ─── Section Definition & Ordering ────────────────────────────────────────────
// 1. DEV 1ère année
// 2. DEV 2ème année (Full Stack)
// 3. ID 1ère année
// 4. ID 2ème année (Systèmes & Réseaux)
// 5. GE 1ère année
// 6. GE 2ème année
// 7. GE 3ème année
// 8. TSM
const SECTIONS = [
  { id: 'dev_1', order: 1, title: 'DÉVELOPPEMENT DIGITAL — 1ÈRE ANNÉE', short: 'DEV 1ère Année' },
  { id: 'dev_2', order: 2, title: 'DÉVELOPPEMENT DIGITAL — 2ÈME ANNÉE (OPTION WEB FULL STACK)', short: 'DEV 2ème Année' },
  { id: 'id_1',  order: 3, title: 'INFRASTRUCTURE DIGITALE — 1ÈRE ANNÉE', short: 'ID 1ère Année' },
  { id: 'id_2',  order: 4, title: 'INFRASTRUCTURE DIGITALE — 2ÈME ANNÉE (SYSTÈMES & RÉSEAUX)', short: 'ID 2ème Année' },
  { id: 'ge_1',  order: 5, title: 'GESTION DES ENTREPRISES — 1ÈRE ANNÉE', short: 'GE 1ère Année' },
  { id: 'ge_2',  order: 6, title: 'GESTION DES ENTREPRISES — 2ÈME ANNÉE', short: 'GE 2ème Année' },
  { id: 'ge_3',  order: 7, title: 'GESTION DES ENTREPRISES — 3ÈME ANNÉE', short: 'GE 3ème Année' },
  { id: 'tsm',   order: 8, title: 'TECHNICIEN SPÉCIALISÉ EN MULTIMÉDIA', short: 'TSM Multimédia' },
  { id: 'autre', order: 9, title: 'AUTRES SECTIONS', short: 'Autres' },
]

const getSectionForGroupe = (g) => {
  const code = (g.code || '').trim()
  const annee = g.annee_etude || (code.includes('1') ? 1 : 2)

  if (code.startsWith('DEVOW') || (code.startsWith('DEV') && annee === 2)) {
    return 'dev_2'
  }
  if (code.startsWith('DEV')) {
    return 'dev_1'
  }
  if (code.startsWith('IDOSR') || (code.startsWith('ID') && annee === 2)) {
    return 'id_2'
  }
  if (code.startsWith('ID')) {
    return 'id_1'
  }
  if (code.startsWith('GE1') || (code.startsWith('GE') && annee === 1)) {
    return 'ge_1'
  }
  if (code.startsWith('GEOCF2') || code.startsWith('GEOCM2') || (code.startsWith('GEO') && annee === 2)) {
    return 'ge_2'
  }
  if (code.startsWith('GEOCF3') || code.startsWith('GEOCM3') || (code.startsWith('GEO') && annee === 3)) {
    return 'ge_3'
  }
  if (code.startsWith('TSM')) {
    return 'tsm'
  }
  return 'autre'
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const formatDate = d => d ? new Date(d).toLocaleDateString('fr-MA', { day: '2-digit', month: '2-digit', year: 'numeric' }) : ''

const apiFetch = async (url, opts = {}) => {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!r.ok) {
    let errMsg = 'Erreur serveur'
    try { const e = await r.json(); errMsg = e.error || e.message || errMsg } catch {}
    throw new Error(errMsg)
  }
  return r.json()
}

// Format Group display: DEVOWFS201 -> NTIC2-FS201, DEV101 -> NTIC2-DEV101, etc.
const formatGroupeDisplay = (code) => {
  if (!code) return ''
  if (code.startsWith('NTIC2-')) return code
  if (code.startsWith('DEVOW')) return `NTIC2-${code.replace('DEVOW', '')}`
  if (code.startsWith('GEO')) return `NTIC2-${code.replace('GEO', '')}`
  if (code.startsWith('IDO')) return `NTIC2-${code.replace('IDO', '')}`
  return `NTIC2-${code}`
}

// Format Prof name for table cell: extract last name or compound name (e.g., EL HAKIKI, DAOUDI, TITOUICH)
const formatProfDisplay = (profs) => {
  if (!profs || profs.length === 0) return ''
  return profs.map(p => {
    const raw = (p.prof_nom || '').trim()
    if (!raw) return ''
    const parts = raw.split(/\s+/)
    if (parts.length <= 1) return raw.toUpperCase()
    const upperParts = parts.map(x => x.toUpperCase())
    const elIdx = upperParts.findIndex(x => ['EL', 'AL', 'BEN', 'AIT'].includes(x))
    if (elIdx !== -1 && upperParts[elIdx + 1]) {
      return `${upperParts[elIdx]} ${upperParts[elIdx + 1]}`
    }
    return upperParts[upperParts.length - 1]
  }).join(' / ')
}

// ─── Toast Container ──────────────────────────────────────────────────────────
function ToastContainer({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>
          {t.message}
        </div>
      ))}
    </div>
  )
}

// ─── Edit Modal ───────────────────────────────────────────────────────────────
function EditModal({ seance, unites, salles, creneaux, professeurs, onClose, onSave, onDelete }) {
  const [uniteId, setUniteId] = useState(seance.unite_id || '')
  const [creneauId, setCreneauId] = useState(seance.creneau_id)
  const [salleId, setSalleId] = useState(seance.salle_id || '')
  const [profId, setProfId] = useState(seance.professeurs?.[0]?.prof_id || '')
  const [mode, setMode] = useState(seance.mode || 'presentiel')
  const [statut, setStatut] = useState(seance.statut || 'brouillon')
  const [loading, setLoading] = useState(false)

  // Filter modules relevant to this group/filiere
  const relevantUnites = useMemo(() => {
    if (!unites || unites.length === 0) return []
    const gCode = seance.groupes?.[0]?.groupe_code
    if (gCode) {
      const match = unites.filter(u => (u.groupes || '').includes(gCode) || u.filiere_code === seance.filiere_code)
      if (match.length > 0) return match
    }
    return unites
  }, [unites, seance])

  const handleSave = async () => {
    setLoading(true)
    try {
      await apiFetch(`${API}/seances/${seance.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          unite_id: uniteId ? +uniteId : seance.unite_id,
          creneau_id: +creneauId,
          salle_id: (mode === 'presentiel' && salleId) ? +salleId : null,
          professeur_id: profId ? +profId : null,
          mode,
          statut,
        })
      })
      onSave()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <h3>Modifier la séance</h3>
        <div style={{ background: '#f8fafc', borderRadius: 8, padding: '12px 16px', marginBottom: 16, fontSize: 13, border: '1px solid #cbd5e1' }}>
          <div>Groupe : <strong>{seance.groupes?.map(g => formatGroupeDisplay(g.groupe_code)).join(', ') || '—'}</strong></div>
          <div style={{ color: '#475569', fontSize: 12, marginTop: 4 }}>
            Filière : <strong>{seance.filiere_nom || seance.filiere_code}</strong>
          </div>
        </div>

        <div className="modal-field">
          <label>Module / Matière</label>
          <select value={uniteId} onChange={e => setUniteId(e.target.value)}>
            {relevantUnites.map(u => (
              <option key={u.id} value={u.id}>
                {u.module_nom} ({u.module_code})
              </option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Jour et Créneau horaire</label>
          <select value={creneauId} onChange={e => setCreneauId(e.target.value)}>
            {creneaux.map(c => {
              const jourLabel = JOURS.find(j => j.id === c.jour)?.nom || `Jour ${c.jour}`
              const horaire = getSlotHoraire(c.jour, c.numero_seance)
              return (
                <option key={c.id} value={c.id}>
                  {jourLabel} — Séance {c.numero_seance} ({horaire})
                </option>
              )
            })}
          </select>
        </div>

        <div className="modal-field">
          <label>Formateur</label>
          <select value={profId} onChange={e => setProfId(e.target.value)}>
            <option value="">— Aucun / Garder actuel —</option>
            {professeurs.map(p => (
              <option key={p.id} value={p.id}>{p.nom_complet}</option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Mode de formation</label>
          <select value={mode} onChange={e => setMode(e.target.value)}>
            <option value="presentiel">Présentiel</option>
            <option value="distance">À distance (TEAM)</option>
          </select>
        </div>

        {mode === 'presentiel' && (
          <div className="modal-field">
            <label>Salle</label>
            <select value={salleId} onChange={e => setSalleId(e.target.value)}>
              <option value="">— Sélectionner une salle —</option>
              {salles.map(s => (
                <option key={s.id} value={s.id}>{s.nom} ({s.type_code})</option>
              ))}
            </select>
          </div>
        )}

        <div className="modal-field">
          <label>Statut</label>
          <select value={statut} onChange={e => setStatut(e.target.value)}>
            <option value="brouillon">Brouillon</option>
            <option value="valide">Validé</option>
          </select>
        </div>

        <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => onDelete(seance)}
          >
            Supprimer la séance
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={loading}>
              {loading ? 'Enregistrement…' : 'Enregistrer les modifications'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Add Session Modal ────────────────────────────────────────────────────────
function AddModal({ prefill, semaine, unites, salles, creneaux, professeurs, groupes, onClose, onSave }) {
  const [groupeId, setGroupeId] = useState(prefill?.groupe?.id || (groupes?.[0]?.id || ''))
  const [uniteId, setUniteId] = useState('')
  const [creneauId, setCreneauId] = useState(prefill?.creneauId || (creneaux?.[0]?.id || ''))
  const [salleId, setSalleId] = useState('')
  const [profId, setProfId] = useState('')
  const [mode, setMode] = useState('presentiel')
  const [loading, setLoading] = useState(false)

  const selectedGroupe = useMemo(() => {
    return groupes.find(g => g.id === +groupeId) || prefill?.groupe
  }, [groupes, groupeId, prefill])

  // Filter unites for the chosen group
  const filteredUnites = useMemo(() => {
    if (!selectedGroupe?.code) return unites
    const gCode = selectedGroupe.code
    const relevant = unites.filter(u => (u.groupes || '').includes(gCode) || u.filiere_code === selectedGroupe.filiere_code)
    return relevant.length > 0 ? relevant : unites
  }, [unites, selectedGroupe])

  useEffect(() => {
    if (filteredUnites.length > 0) {
      setUniteId(filteredUnites[0].id)
    }
  }, [filteredUnites])

  const handleCreate = async () => {
    if (!uniteId || !creneauId || !groupeId) {
      alert('Veuillez sélectionner un groupe, un module et un créneau')
      return
    }
    setLoading(true)
    try {
      await apiFetch(`${API}/seances`, {
        method: 'POST',
        body: JSON.stringify({
          unite_id: +uniteId,
          semaine_id: semaine.id,
          creneau_id: +creneauId,
          salle_id: (mode === 'presentiel' && salleId) ? +salleId : null,
          mode,
          nature: 'simple',
          groupe_ids: [+groupeId],
          professeur_ids: profId ? [+profId] : [],
        })
      })
      onSave()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <h3>Ajouter une séance</h3>

        <div className="modal-field">
          <label>Groupe</label>
          <select value={groupeId} onChange={e => setGroupeId(e.target.value)}>
            {groupes.map(g => (
              <option key={g.id} value={g.id}>
                {formatGroupeDisplay(g.code)} — {g.filiere_nom || g.filiere_code}
              </option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Jour et Créneau horaire</label>
          <select value={creneauId} onChange={e => setCreneauId(e.target.value)}>
            {creneaux.map(c => {
              const jourLabel = JOURS.find(j => j.id === c.jour)?.nom || `Jour ${c.jour}`
              const horaire = getSlotHoraire(c.jour, c.numero_seance)
              return (
                <option key={c.id} value={c.id}>
                  {jourLabel} — Séance {c.numero_seance} ({horaire})
                </option>
              )
            })}
          </select>
        </div>

        <div className="modal-field">
          <label>Module / Matière</label>
          <select value={uniteId} onChange={e => setUniteId(e.target.value)}>
            {filteredUnites.map(u => (
              <option key={u.id} value={u.id}>
                {u.module_nom} ({u.module_code})
              </option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Formateur</label>
          <select value={profId} onChange={e => setProfId(e.target.value)}>
            <option value="">— Sélectionner un formateur —</option>
            {professeurs.map(p => (
              <option key={p.id} value={p.id}>{p.nom_complet}</option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Mode de formation</label>
          <select value={mode} onChange={e => setMode(e.target.value)}>
            <option value="presentiel">Présentiel</option>
            <option value="distance">À distance (TEAM)</option>
          </select>
        </div>

        {mode === 'presentiel' && (
          <div className="modal-field">
            <label>Salle</label>
            <select value={salleId} onChange={e => setSalleId(e.target.value)}>
              <option value="">— Sélectionner une salle —</option>
              {salles.map(s => (
                <option key={s.id} value={s.id}>{s.nom} ({s.type_code})</option>
              ))}
            </select>
          </div>
        )}

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="button" className="btn btn-primary" onClick={handleCreate} disabled={loading}>
            {loading ? 'Création…' : 'Créer la séance'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Select Session to Modify Modal ──────────────────────────────────────────
function SelectModifyModal({ seances, groupes, onClose, onSelectSeance }) {
  const [filterGId, setFilterGId] = useState('all')
  const [selectedSeanceId, setSelectedSeanceId] = useState('')

  const availableSeances = useMemo(() => {
    return seances.filter(s => {
      if (filterGId !== 'all' && !s.groupes?.some(g => String(g.groupe_id) === String(filterGId))) {
        return false
      }
      return true
    })
  }, [seances, filterGId])

  useEffect(() => {
    if (availableSeances.length > 0) {
      setSelectedSeanceId(availableSeances[0].id)
    } else {
      setSelectedSeanceId('')
    }
  }, [availableSeances])

  const handleConfirm = () => {
    const s = seances.find(x => x.id === +selectedSeanceId)
    if (s) {
      onSelectSeance(s)
      onClose()
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <h3>Sélectionner la séance à modifier</h3>
        <p style={{ fontSize: 13, color: '#64748b', marginTop: -6, marginBottom: 16 }}>
          Choisissez la séance à modifier dans la liste ou cliquez directement dessus dans le tableau :
        </p>

        <div className="modal-field">
          <label>Filtrer par Groupe</label>
          <select value={filterGId} onChange={e => setFilterGId(e.target.value)}>
            <option value="all">Tous les groupes ({seances.length} séances)</option>
            {groupes.map(g => (
              <option key={g.id} value={g.id}>
                {formatGroupeDisplay(g.code)} — {g.filiere_nom || g.filiere_code}
              </option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Séance ({availableSeances.length} trouvée(s))</label>
          <select
            value={selectedSeanceId}
            onChange={e => setSelectedSeanceId(e.target.value)}
            style={{ height: 42 }}
          >
            {availableSeances.length === 0 ? (
              <option value="">Aucune séance trouvée</option>
            ) : (
              availableSeances.map(s => {
                const jourNom = JOURS.find(j => j.id === s.jour)?.nom || `Jour ${s.jour}`
                const horaire = getSlotHoraire(s.jour, s.numero_seance)
                const gLabel = s.groupes?.map(g => formatGroupeDisplay(g.groupe_code)).join(', ') || ''
                const pLabel = s.professeurs?.map(p => p.prof_nom).join(', ') || 'Sans formateur'
                return (
                  <option key={s.id} value={s.id}>
                    {gLabel} | {jourNom} S{s.numero_seance} ({horaire}) : {s.module_intitule || s.module_code} ({pLabel})
                  </option>
                )
              })
            )}
          </select>
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleConfirm}
            disabled={!selectedSeanceId}
          >
            Ouvrir la modification
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Modal Créer / Modifier Groupe ───────────────────────────────────────────
function GroupeModal({ groupe, filieres, onClose, onSave }) {
  const isEdit = Boolean(groupe?.id)
  const [code, setCode] = useState(groupe?.code || '')
  const [filiereId, setFiliereId] = useState(groupe?.filiere_id || (filieres?.[0]?.id || ''))
  const [anneeEtude, setAnneeEtude] = useState(groupe?.annee_etude || 1)
  const [effectif, setEffectif] = useState(groupe?.effectif ?? 25)
  const [regime, setRegime] = useState(groupe?.regime || 'CDJ')
  const [modeFormation, setModeFormation] = useState(groupe?.mode_formation || 'Résidentiel')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!filiereId && filieres.length > 0) {
      setFiliereId(filieres[0].id)
    }
  }, [filieres, filiereId])

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!code.trim()) {
      setError('Veuillez saisir le code du groupe (ex: DEV105, ID201)')
      return
    }
    if (!filiereId) {
      setError('Veuillez sélectionner une filière')
      return
    }

    setLoading(true)
    setError('')
    try {
      const payload = {
        code: code.trim().toUpperCase(),
        filiere_id: +filiereId,
        annee_etude: +anneeEtude,
        effectif: +effectif,
        regime,
        mode_formation: modeFormation,
      }

      let res
      if (isEdit) {
        res = await apiFetch(`${API}/groupes/${groupe.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
      } else {
        res = await apiFetch(`${API}/groupes`, {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      }
      onSave(res, isEdit)
    } catch (err) {
      setError(err.message || 'Une erreur est survenue')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: '#0f2d5e' }}>
            {isEdit ? `Modifier le groupe ${groupe.code}` : 'Ajouter un Nouveau Groupe'}
          </h3>
          <button
            onClick={onClose}
            type="button"
            style={{ fontSize: 20, color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', lineHeight: 1 }}
          >
            
          </button>
        </div>

        {error && (
          <div className="alert-banner error" style={{ marginBottom: 16 }}>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="modal-field">
            <label>Code du Groupe * (ex: DEV101, ID201, TSM101)</label>
            <input
              type="text"
              placeholder="Ex: DEV105"
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase())}
              required
              autoFocus
            />
          </div>

          <div className="modal-field">
            <label>Filière *</label>
            <select value={filiereId} onChange={e => setFiliereId(e.target.value)} required>
              {filieres.map(f => (
                <option key={f.id} value={f.id}>
                  {f.intitule} ({f.code})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="modal-field">
              <label>Année d'étude</label>
              <select value={anneeEtude} onChange={e => setAnneeEtude(e.target.value)}>
                <option value={1}>1ère Année</option>
                <option value={2}>2ème Année</option>
                <option value={3}>3ème Année</option>
              </select>
            </div>

            <div className="modal-field">
              <label>Effectif (stagiaires)</label>
              <input
                type="number"
                min="1"
                max="100"
                value={effectif}
                onChange={e => setEffectif(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="modal-field">
              <label>Régime</label>
              <select value={regime} onChange={e => setRegime(e.target.value)}>
                <option value="CDJ">CDJ (Cours de Jour)</option>
                <option value="CDS">CDS (Cours du Soir)</option>
              </select>
            </div>

            <div className="modal-field">
              <label>Mode de formation</label>
              <select value={modeFormation} onChange={e => setModeFormation(e.target.value)}>
                <option value="Résidentiel">Résidentiel</option>
                <option value="Alterné">Alterné</option>
              </select>
            </div>
          </div>

          <div className="modal-actions" style={{ marginTop: 24 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Enregistrement…' : (isEdit ? 'Enregistrer les modifications' : 'Créer le groupe')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Modal Confirmation Suppression Groupe ──────────────────────────────────
function DeleteGroupeModal({ groupe, onClose, onConfirm, loading }) {
  if (!groupe) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
        <h3 style={{ margin: 0, fontSize: 18, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 8 }}>
          Confirmer la suppression
        </h3>
        <p style={{ margin: '16px 0 8px', fontSize: 14, color: '#334155', lineHeight: 1.5 }}>
          Êtes-vous sûr de vouloir supprimer le groupe <strong>{formatGroupeDisplay(groupe.code)}</strong> ({groupe.filiere_nom || groupe.filiere_code}) ?
        </p>
        <p style={{ margin: '0 0 20px', fontSize: 12, color: '#64748b', background: '#f8fafc', padding: 10, borderRadius: 6, border: '1px solid #e2e8f0', lineHeight: 1.4 }}>
          S'il existe des séances enregistrées pour ce groupe, il sera archivé en toute sécurité sans altérer l'historique de l'emploi du temps.
        </p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
            Annuler
          </button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={loading}>
            {loading ? 'Suppression…' : 'Oui, supprimer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Modal Créer / Modifier Formateur ─────────────────────────────────────────
function ProfesseurModal({ prof, onClose, onSave }) {
  const isEdit = Boolean(prof?.id)
  const [nomComplet, setNomComplet] = useState(prof?.nom_complet || '')
  const [matricule, setMatricule] = useState(prof?.matricule || '')
  const [email, setEmail] = useState(prof?.email || '')
  const [statut, setStatut] = useState(prof?.statut || 'permanent')
  const [tauxPresence, setTauxPresence] = useState(prof?.taux_presence ?? 100)
  const [heuresMax, setHeuresMax] = useState(prof?.heures_max_semaine || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!nomComplet.trim()) {
      setError('Veuillez saisir le nom complet du formateur')
      return
    }

    setLoading(true)
    setError('')
    try {
      const payload = {
        nom_complet: nomComplet.trim().toUpperCase(),
        matricule: matricule.trim(),
        email: email.trim(),
        statut,
        taux_presence: +tauxPresence,
        heures_max_semaine: heuresMax ? +heuresMax : null,
      }

      let res
      if (isEdit) {
        res = await apiFetch(`${API}/professeurs/${prof.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
      } else {
        res = await apiFetch(`${API}/professeurs`, {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      }
      onSave(res, isEdit)
    } catch (err) {
      setError(err.message || 'Une erreur est survenue')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: '#0f2d5e' }}>
            {isEdit ? `Modifier le Formateur` : 'Ajouter un Formateur'}
          </h3>
          <button
            onClick={onClose}
            type="button"
            style={{ fontSize: 20, color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', lineHeight: 1 }}
          >
            
          </button>
        </div>

        {error && (
          <div className="alert-banner error" style={{ marginBottom: 16 }}>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="modal-field">
            <label>Nom Complet du Formateur *</label>
            <input
              type="text"
              placeholder="Ex: MOHAMMED BENALI"
              value={nomComplet}
              onChange={e => setNomComplet(e.target.value.toUpperCase())}
              required
              autoFocus
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="modal-field">
              <label>Matricule (optionnel, auto si vide)</label>
              <input
                type="text"
                placeholder="Ex: 10452"
                value={matricule}
                onChange={e => setMatricule(e.target.value)}
              />
            </div>

            <div className="modal-field">
              <label>Statut</label>
              <select value={statut} onChange={e => setStatut(e.target.value)}>
                <option value="permanent">Permanent</option>
                <option value="vacataire">Vacataire</option>
              </select>
            </div>
          </div>

          <div className="modal-field">
            <label>Email professionnel</label>
            <input
              type="email"
              placeholder="Ex: m.benali@ofppt.ma"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="modal-field">
              <label>Taux de Présence (%)</label>
              <input
                type="number"
                min="0"
                max="100"
                value={tauxPresence}
                onChange={e => setTauxPresence(e.target.value)}
              />
            </div>

            <div className="modal-field">
              <label>Heures max / semaine</label>
              <input
                type="number"
                placeholder="Ex: 20 (optionnel)"
                value={heuresMax}
                onChange={e => setHeuresMax(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-actions" style={{ marginTop: 24 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Enregistrement…' : (isEdit ? 'Enregistrer les modifications' : 'Créer le formateur')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Modal Confirmation Suppression Formateur ────────────────────────────────
function DeleteProfesseurModal({ prof, onClose, onConfirm, loading }) {
  if (!prof) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
        <h3 style={{ margin: 0, fontSize: 18, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 8 }}>
          Confirmer la suppression
        </h3>
        <p style={{ margin: '16px 0 8px', fontSize: 14, color: '#334155', lineHeight: 1.5 }}>
          Êtes-vous sûr de vouloir supprimer le formateur <strong>{prof.nom_complet}</strong> (Mle: {prof.matricule || '—'}) ?
        </p>
        <p style={{ margin: '0 0 20px', fontSize: 12, color: '#64748b', background: '#f8fafc', padding: 10, borderRadius: 6, border: '1px solid #e2e8f0', lineHeight: 1.4 }}>
          S'il a déjà des séances planifiées dans les emplois du temps, il sera désactivé en toute sécurité pour préserver l'historique pédagogique.
        </p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
            Annuler
          </button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={loading}>
            {loading ? 'Suppression…' : 'Oui, supprimer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Modal Créer / Modifier Salle ─────────────────────────────────────────────
function SalleModal({ salle, typesSalles, onClose, onSave }) {
  const isEdit = Boolean(salle?.id)
  const [nom, setNom] = useState(salle?.nom || '')
  const [typeSalleId, setTypeSalleId] = useState(salle?.type_salle_id || (typesSalles?.[0]?.id || ''))
  const [capacite, setCapacite] = useState(salle?.capacite ?? 30)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!typeSalleId && typesSalles?.length > 0) {
      setTypeSalleId(typesSalles[0].id)
    }
  }, [typesSalles, typeSalleId])

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!nom.trim()) {
      setError('Veuillez renseigner le nom de la salle (ex: SC12, SP5, LABO1)')
      return
    }
    if (!typeSalleId) {
      setError('Veuillez sélectionner un type de salle')
      return
    }

    setLoading(true)
    setError('')
    try {
      const payload = {
        nom: nom.trim().toUpperCase(),
        type_salle_id: +typeSalleId,
        capacite: +capacite,
      }

      let res
      if (isEdit) {
        res = await apiFetch(`${API}/salles/${salle.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        })
      } else {
        res = await apiFetch(`${API}/salles`, {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      }
      onSave(res, isEdit)
    } catch (err) {
      setError(err.message || 'Une erreur est survenue')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 460 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: '#0f2d5e' }}>
            {isEdit ? `Modifier la Salle ${salle.nom}` : 'Ajouter une Salle'}
          </h3>
          <button
            onClick={onClose}
            type="button"
            style={{ fontSize: 20, color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', lineHeight: 1 }}
          >
            
          </button>
        </div>

        {error && (
          <div className="alert-banner error" style={{ marginBottom: 16 }}>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="modal-field">
            <label>Nom ou Numéro de la Salle * (ex: SC1, SP3, LABO2)</label>
            <input
              type="text"
              placeholder="Ex: SC12"
              value={nom}
              onChange={e => setNom(e.target.value.toUpperCase())}
              required
              autoFocus
            />
          </div>

          <div className="modal-field">
            <label>Type de Salle *</label>
            <select value={typeSalleId} onChange={e => setTypeSalleId(e.target.value)} required>
              {typesSalles?.map(t => (
                <option key={t.id} value={t.id}>
                  {t.libelle} ({t.code})
                </option>
              ))}
            </select>
          </div>

          <div className="modal-field">
            <label>Capacité (nombre de places)</label>
            <input
              type="number"
              min="1"
              max="200"
              value={capacite}
              onChange={e => setCapacite(e.target.value)}
            />
          </div>

          <div className="modal-actions" style={{ marginTop: 24 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Enregistrement…' : (isEdit ? 'Enregistrer les modifications' : 'Créer la salle')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Modal Confirmation Suppression Salle ────────────────────────────────────
function DeleteSalleModal({ salle, onClose, onConfirm, loading }) {
  if (!salle) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
        <h3 style={{ margin: 0, fontSize: 18, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 8 }}>
          Confirmer la suppression
        </h3>
        <p style={{ margin: '16px 0 8px', fontSize: 14, color: '#334155', lineHeight: 1.5 }}>
          Êtes-vous sûr de vouloir supprimer la salle <strong>{salle.nom}</strong> ({salle.type_libelle || salle.type_code}) ?
        </p>
        <p style={{ margin: '0 0 20px', fontSize: 12, color: '#64748b', background: '#f8fafc', padding: 10, borderRadius: 6, border: '1px solid #e2e8f0', lineHeight: 1.4 }}>
          Si des séances passées ou planifiées utilisent cette salle, elle sera archivée en toute sécurité.
        </p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
            Annuler
          </button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={loading}>
            {loading ? 'Suppression…' : 'Oui, supprimer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard({ role = 'admin', onLogout }) {
  const [activeNav, setActiveNav] = useState('emploi')
  const [semaines, setSemaines] = useState([])
  const [selectedSemaine, setSelectedSemaine] = useState(null)
  const [seances, setSeances] = useState([])
  const [groupes, setGroupes] = useState([])
  const [professeurs, setProfesseurs] = useState([])
  const [salles, setSalles] = useState([])
  const [typesSalles, setTypesSalles] = useState([])
  const [creneaux, setCreneaux] = useState([])
  const [unites, setUnites] = useState([])
  const [filieres, setFilieres] = useState([])
  const [stats, setStats] = useState(null)

  // Filters
  const [selectedSectionFilter, setSelectedSectionFilter] = useState('all')
  const [searchGroupe, setSearchGroupe] = useState('')

  // State flags & Modals
  const [loadingSeances, setLoadingSeances] = useState(false)
  const [loadingGen, setLoadingGen] = useState(false)
  const [editSeance, setEditSeance] = useState(null)
  const [openSelectModify, setOpenSelectModify] = useState(false)
  const [addPrefill, setAddPrefill] = useState(null)

  // Groupe CRUD Modals & Filters
  const [groupeModalOpen, setGroupeModalOpen] = useState(false)
  const [editingGroupe, setEditingGroupe] = useState(null)
  const [deletingGroupe, setDeletingGroupe] = useState(null)
  const [deletingLoading, setDeletingLoading] = useState(false)
  const [groupeSearch, setGroupeSearch] = useState('')
  const [groupeFiliereFilter, setGroupeFiliereFilter] = useState('all')
  const [groupeAnneeFilter, setGroupeAnneeFilter] = useState('all')

  // Formateur CRUD Modals & Filters
  const [profModalOpen, setProfModalOpen] = useState(false)
  const [editingProf, setEditingProf] = useState(null)
  const [deletingProf, setDeletingProf] = useState(null)
  const [deletingProfLoading, setDeletingProfLoading] = useState(false)
  const [profSearch, setProfSearch] = useState('')
  const [profStatutFilter, setProfStatutFilter] = useState('all')

  // Salle CRUD Modals & Filters
  const [salleModalOpen, setSalleModalOpen] = useState(false)
  const [editingSalle, setEditingSalle] = useState(null)
  const [deletingSalle, setDeletingSalle] = useState(null)
  const [deletingSalleLoading, setDeletingSalleLoading] = useState(false)
  const [salleSearch, setSalleSearch] = useState('')
  const [salleTypeFilter, setSalleTypeFilter] = useState('all')

  const [toasts, setToasts] = useState([])
  const [dbStatus, setDbStatus] = useState(null)

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts(t => [...t, { id, message, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000)
  }, [])

  // Load static data
  useEffect(() => {
    const init = async () => {
      try {
        const [sw, g, p, sl, cr, u, f, ts, hc] = await Promise.all([
          apiFetch(`${API}/semaines`),
          apiFetch(`${API}/groupes`),
          apiFetch(`${API}/professeurs`),
          apiFetch(`${API}/salles`),
          apiFetch(`${API}/creneaux`),
          apiFetch(`${API}/unites`).catch(() => []),
          apiFetch(`${API}/filieres`).catch(() => []),
          apiFetch(`${API}/types-salles`).catch(() => []),
          apiFetch(`${API}/health`),
        ])
        setSemaines(sw)
        setGroupes(g)
        setProfesseurs(p)
        setSalles(sl)
        setCreneaux(cr)
        setUnites(u)
        setFilieres(f)
        setTypesSalles(ts)
        setDbStatus(hc.status)
        if (sw.length > 0) setSelectedSemaine(sw[0])
      } catch (e) {
        setDbStatus('error')
        addToast('Impossible de joindre le serveur backend.', 'error')
      }
    }
    init()
  }, [addToast])

  // Load sessions when week changes
  const loadWeekData = useCallback(async (semaineId) => {
    if (!semaineId) return
    setLoadingSeances(true)
    try {
      const [sc, st] = await Promise.all([
        apiFetch(`${API}/emploi-du-temps/${semaineId}`),
        apiFetch(`${API}/stats/${semaineId}`).catch(() => null),
      ])
      setSeances(sc)
      setStats(st)
    } catch (e) {
      addToast(e.message, 'error')
    } finally {
      setLoadingSeances(false)
    }
  }, [addToast])

  useEffect(() => {
    if (selectedSemaine) {
      loadWeekData(selectedSemaine.id)
    }
  }, [selectedSemaine, loadWeekData])

  const refreshSeances = useCallback(() => {
    if (selectedSemaine) loadWeekData(selectedSemaine.id)
  }, [selectedSemaine, loadWeekData])

  // Generator for current week
  const handleGenerate = async () => {
    if (!selectedSemaine) return
    if (!window.confirm(`Générer automatiquement l'emploi du temps pour la Semaine ${selectedSemaine.numero} ?\nLes séances brouillon non verrouillées de cette semaine seront recalculées.`)) return
    setLoadingGen(true)
    try {
      const res = await apiFetch(`${API}/generer/${selectedSemaine.id}`, { method: 'POST' })
      addToast(res.message, 'success')
      refreshSeances()
    } catch (e) {
      addToast(e.message, 'error')
    } finally {
      setLoadingGen(false)
    }
  }

  // Validate all sessions for current week
  const handleValider = async () => {
    if (!selectedSemaine) return
    if (!window.confirm(`Valider toutes les séances de la Semaine ${selectedSemaine.numero} ?`)) return
    try {
      await apiFetch(`${API}/semaines/${selectedSemaine.id}/valider`, { method: 'POST' })
      addToast('Emploi du temps validé avec succès', 'success')
      refreshSeances()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  // Clear current week
  const handleVider = async () => {
    if (!selectedSemaine) return
    if (!window.confirm(`Attention : Vider toutes les séances de la Semaine ${selectedSemaine.numero} ?`)) return
    try {
      await apiFetch(`${API}/vider-semaine/${selectedSemaine.id}`, { method: 'POST' })
      addToast('Toutes les séances de la semaine ont été effacées', 'warning')
      refreshSeances()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  // Delete single session
  const handleDelete = async (seance) => {
    if (!window.confirm(`Supprimer la séance : ${seance.module_intitule || seance.module_code} ?`)) return
    try {
      await apiFetch(`${API}/seances/${seance.id}`, { method: 'DELETE' })
      addToast('Séance supprimée', 'warning')
      setEditSeance(null)
      refreshSeances()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  // Handle cell click on empty slot to add session
  const handleCellClickEmpty = (groupe, jour, seanceNum) => {
    const creneau = creneaux.find(c => c.jour === jour && c.numero_seance === seanceNum)
    setAddPrefill({
      groupe,
      jour,
      seance: seanceNum,
      creneauId: creneau?.id,
    })
  }

  // Handle direct click on 'Ajouter une séance' button
  const handleAddDirect = () => {
    setAddPrefill({
      groupe: groupes[0] || null,
      jour: 1,
      seance: 1,
      creneauId: creneaux[0]?.id,
    })
  }

  // Groupe CRUD handlers
  const handleSaveGroupe = (savedGroupe, isEdit) => {
    if (isEdit) {
      setGroupes(prev => prev.map(g => g.id === savedGroupe.id ? savedGroupe : g))
      addToast(`Groupe ${savedGroupe.code} modifié avec succès`, 'success')
    } else {
      setGroupes(prev => [...prev, savedGroupe].sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true })))
      addToast(`Groupe ${savedGroupe.code} créé avec succès`, 'success')
    }
    setGroupeModalOpen(false)
    setEditingGroupe(null)
  }

  const handleDeleteGroupeConfirm = async () => {
    if (!deletingGroupe) return
    setDeletingLoading(true)
    try {
      const res = await apiFetch(`${API}/groupes/${deletingGroupe.id}`, { method: 'DELETE' })
      setGroupes(prev => prev.filter(g => g.id !== deletingGroupe.id))
      addToast(res.message || `Groupe ${deletingGroupe.code} supprimé avec succès`, 'success')
      setDeletingGroupe(null)
    } catch (err) {
      addToast(err.message || 'Erreur lors de la suppression du groupe', 'error')
    } finally {
      setDeletingLoading(false)
    }
  }

  const filteredGroupesList = useMemo(() => {
    return groupes.filter(g => {
      const q = (groupeSearch || '').trim().toLowerCase()
      const matchSearch = !q ||
        (g.code && g.code.toLowerCase().includes(q)) ||
        formatGroupeDisplay(g.code).toLowerCase().includes(q) ||
        (g.filiere_nom && g.filiere_nom.toLowerCase().includes(q)) ||
        (g.filiere_code && g.filiere_code.toLowerCase().includes(q))

      const matchFiliere = groupeFiliereFilter === 'all' ||
        String(g.filiere_id) === String(groupeFiliereFilter) ||
        g.filiere_code === groupeFiliereFilter

      const matchAnnee = groupeAnneeFilter === 'all' ||
        String(g.annee_etude) === String(groupeAnneeFilter)

      return matchSearch && matchFiliere && matchAnnee
    })
  }, [groupes, groupeSearch, groupeFiliereFilter, groupeAnneeFilter])

  // Professeur CRUD handlers
  const handleSaveProf = (savedProf, isEdit) => {
    if (isEdit) {
      setProfesseurs(prev => prev.map(p => p.id === savedProf.id ? savedProf : p))
      addToast(`Formateur ${savedProf.nom_complet} modifié avec succès`, 'success')
    } else {
      setProfesseurs(prev => [...prev, savedProf].sort((a, b) => a.nom_complet.localeCompare(b.nom_complet)))
      addToast(`Formateur ${savedProf.nom_complet} créé avec succès`, 'success')
    }
    setProfModalOpen(false)
    setEditingProf(null)
  }

  const handleDeleteProfConfirm = async () => {
    if (!deletingProf) return
    setDeletingProfLoading(true)
    try {
      const res = await apiFetch(`${API}/professeurs/${deletingProf.id}`, { method: 'DELETE' })
      setProfesseurs(prev => prev.filter(p => p.id !== deletingProf.id))
      addToast(res.message || `Formateur ${deletingProf.nom_complet} supprimé avec succès`, 'success')
      setDeletingProf(null)
    } catch (err) {
      addToast(err.message || 'Erreur lors de la suppression du formateur', 'error')
    } finally {
      setDeletingProfLoading(false)
    }
  }

  const filteredProfsList = useMemo(() => {
    return professeurs.filter(p => {
      const q = (profSearch || '').trim().toLowerCase()
      const matchSearch = !q ||
        (p.nom_complet && p.nom_complet.toLowerCase().includes(q)) ||
        (p.matricule && p.matricule.toLowerCase().includes(q)) ||
        (p.email && p.email.toLowerCase().includes(q))

      const matchStatut = profStatutFilter === 'all' || p.statut === profStatutFilter

      return matchSearch && matchStatut
    })
  }, [professeurs, profSearch, profStatutFilter])

  // Salle CRUD handlers
  const handleSaveSalle = (savedSalle, isEdit) => {
    if (isEdit) {
      setSalles(prev => prev.map(s => s.id === savedSalle.id ? savedSalle : s))
      addToast(`Salle ${savedSalle.nom} modifiée avec succès`, 'success')
    } else {
      setSalles(prev => [...prev, savedSalle].sort((a, b) => a.nom.localeCompare(b.nom, undefined, { numeric: true })))
      addToast(`Salle ${savedSalle.nom} créée avec succès`, 'success')
    }
    setSalleModalOpen(false)
    setEditingSalle(null)
  }

  const handleDeleteSalleConfirm = async () => {
    if (!deletingSalle) return
    setDeletingSalleLoading(true)
    try {
      const res = await apiFetch(`${API}/salles/${deletingSalle.id}`, { method: 'DELETE' })
      setSalles(prev => prev.filter(s => s.id !== deletingSalle.id))
      addToast(res.message || `Salle ${deletingSalle.nom} supprimée avec succès`, 'success')
      setDeletingSalle(null)
    } catch (err) {
      addToast(err.message || 'Erreur lors de la suppression de la salle', 'error')
    } finally {
      setDeletingSalleLoading(false)
    }
  }

  const filteredSallesList = useMemo(() => {
    return salles.filter(s => {
      const q = (salleSearch || '').trim().toLowerCase()
      const matchSearch = !q ||
        (s.nom && s.nom.toLowerCase().includes(q)) ||
        (s.type_libelle && s.type_libelle.toLowerCase().includes(q)) ||
        (s.type_code && s.type_code.toLowerCase().includes(q))

      const matchType = salleTypeFilter === 'all' ||
        String(s.type_salle_id) === String(salleTypeFilter) ||
        s.type_code === salleTypeFilter

      return matchSearch && matchType
    })
  }, [salles, salleSearch, salleTypeFilter])

  // Groupes structured by sections (DEV 1ère, DEV 2ème, ID 1ère, ID 2ème, GE, etc.)
  const groupedSections = useMemo(() => {
    // 1. Group groups by section ID
    const sectionMap = {}
    SECTIONS.forEach(s => { sectionMap[s.id] = [] })

    groupes.forEach(g => {
      const sId = getSectionForGroupe(g)
      if (!sectionMap[sId]) sectionMap[sId] = []
      sectionMap[sId].push(g)
    })

    // 2. Sort groups inside each section naturally
    Object.keys(sectionMap).forEach(k => {
      sectionMap[k].sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }))
    })

    // 3. Build ordered list of sections with filter applied
    const result = []
    SECTIONS.forEach(s => {
      if (selectedSectionFilter !== 'all' && selectedSectionFilter !== s.id) return

      let gList = sectionMap[s.id] || []
      if (searchGroupe.trim()) {
        const query = searchGroupe.trim().toLowerCase()
        gList = gList.filter(g => {
          const fullDisplay = formatGroupeDisplay(g.code).toLowerCase()
          const rawCode = (g.code || '').toLowerCase()
          return fullDisplay.includes(query) || rawCode.includes(query)
        })
      }

      if (gList.length > 0) {
        result.push({
          ...s,
          groupes: gList
        })
      }
    })

    return result
  }, [groupes, selectedSectionFilter, searchGroupe])

  // Lookup map: for fast rendering:
  // key: `${groupe.id}_${jour}_${seanceNum}` -> seance
  const seanceMap = useMemo(() => {
    const map = {}
    for (const s of seances) {
      for (const g of (s.groupes || [])) {
        const key = `${g.groupe_id}_${s.jour}_${s.numero_seance}`
        map[key] = s
      }
    }
    return map
  }, [seances])

  // Export CSV in the EXACT 24-columns layout
  const handleExportCSV = () => {
    if (!selectedSemaine) return
    const headers1 = ['Groupe', 'Information']
    JOURS.forEach(j => {
      headers1.push(j.nom, '', '', '')
    })
    headers1.push('Effectif')

    const headers2 = ['', '']
    JOURS.forEach(() => {
      headers2.push('SEANCE 1', 'SEANCE 2', 'SEANCE 3', 'SEANCE 4')
    })
    headers2.push('')

    const headers3 = ['', '']
    JOURS.forEach(j => {
      for (let s = 1; s <= 4; s++) {
        headers3.push(getSlotHoraire(j.id, s))
      }
    })
    headers3.push('')

    const escapeCsv = cell => `"${String(cell || '').replace(/"/g, '""')}"`

    const rows = [
      headers1.map(escapeCsv).join(';'),
      headers2.map(escapeCsv).join(';'),
      headers3.map(escapeCsv).join(';'),
    ]

    groupedSections.forEach(sec => {
      rows.push([`=== ${sec.title} ===`].map(escapeCsv).join(';'))

      for (const g of sec.groupes) {
        const gCode = formatGroupeDisplay(g.code)

        // Row 1: Formateur
        const r1 = [gCode, 'FORMATEUR']
        ALL_24_SLOTS.forEach(slot => {
          const s = seanceMap[`${g.id}_${slot.jour}_${slot.seance}`]
          r1.push(s ? formatProfDisplay(s.professeurs) : '')
        })
        r1.push(g.effectif || 25)
        rows.push(r1.map(escapeCsv).join(';'))

        // Row 2: Module
        const r2 = ['', 'MODULE']
        ALL_24_SLOTS.forEach(slot => {
          const s = seanceMap[`${g.id}_${slot.jour}_${slot.seance}`]
          r2.push(s ? (s.module_intitule || s.module_code) : '')
        })
        r2.push('')
        rows.push(r2.map(escapeCsv).join(';'))

        // Row 3: Salle
        const r3 = ['', 'SALLE']
        ALL_24_SLOTS.forEach(slot => {
          const s = seanceMap[`${g.id}_${slot.jour}_${slot.seance}`]
          const salle = s ? (s.salle_nom || (s.mode === 'distance' ? 'TEAM' : '—')) : ''
          r3.push(salle)
        })
        r3.push('')
        rows.push(r3.map(escapeCsv).join(';'))
      }
    })

    // Add BOM for Excel UTF-8 compatibility
    const csvContent = '\uFEFF' + rows.join('\r\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.setAttribute('href', url)
    link.setAttribute('download', `Emploi_NTIC2_Semaine_${selectedSemaine.numero}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Week navigation
  const currentWeekIdx = semaines.findIndex(s => s.id === selectedSemaine?.id)
  const prevWeek = () => currentWeekIdx < semaines.length - 1 ? setSelectedSemaine(semaines[currentWeekIdx + 1]) : null
  const nextWeek = () => currentWeekIdx > 0 ? setSelectedSemaine(semaines[currentWeekIdx - 1]) : null

  return (
    <div className="dashboard">
      <ToastContainer toasts={toasts} />

      {/* ── Sidebar ── */}
      <aside className="dash-sidebar">
        <div className="dash-sidebar-logo">
          <div>
            <h2>GestEmploi</h2>
            <span>ISTA NTIC 2</span>
          </div>
        </div>

        <nav className="dash-nav">
          {[
            { id: 'emploi',  label: 'Emploi du temps' },
            { id: 'groupes', label: 'Groupes' },
            { id: 'profs',   label: 'Formateurs' },
            { id: 'salles',  label: 'Salles' },
          ].map(item => (
            <button
              key={item.id}
              className={`dash-nav-item ${activeNav === item.id ? 'active' : ''}`}
              onClick={() => setActiveNav(item.id)}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="dash-sidebar-footer">
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', marginBottom: 10, paddingLeft: 12 }}>
            Base de données: <span style={{ color: dbStatus === 'ok' ? '#4ade80' : '#f87171', fontWeight: 600 }}>
              {dbStatus === 'ok' ? 'Connectée' : 'Erreur'}
            </span>
          </div>
          <button className="dash-logout-btn" onClick={onLogout}>
            <span>Déconnexion</span>
          </button>
        </div>
      </aside>

      {/* ── Main Area ── */}
      <main className="dash-main">
        <header className="dash-topbar">
          <h1>
            {activeNav === 'emploi'  && 'Emploi du temps — ISTA NTIC 2'}
            {activeNav === 'groupes' && 'Gestion des Groupes'}
            {activeNav === 'profs'   && 'Gestion des Formateurs'}
            {activeNav === 'salles'  && 'Salles et Locaux'}
          </h1>
          <div className="topbar-right">
            <span style={{ fontSize: 13, color: '#475569', fontWeight: 500 }}>
              {role === 'admin' ? 'Administrateur' : 'Formateur'}
            </span>
          </div>
        </header>

        <div className="dash-content">
          {activeNav === 'emploi' && (
            <>
              {/* ── Controls Bar ── */}
              <div className="controls-bar">
                {/* Week selector */}
                <div className="week-nav">
                  <button className="btn btn-ghost" onClick={prevWeek} disabled={currentWeekIdx >= semaines.length - 1} title="Semaine précédente">Précédent</button>
                  <select
                    style={{ minWidth: 260, fontWeight: 600 }}
                    value={selectedSemaine?.id || ''}
                    onChange={e => setSelectedSemaine(semaines.find(s => s.id === +e.target.value))}
                  >
                    {semaines.map(s => (
                      <option key={s.id} value={s.id}>
                        Semaine {s.numero} ({formatDate(s.date_debut)} au {formatDate(s.date_fin)})
                      </option>
                    ))}
                  </select>
                  <button className="btn btn-ghost" onClick={nextWeek} disabled={currentWeekIdx <= 0} title="Semaine suivante">Suivant</button>
                </div>

                {/* Section filter */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <label>Section :</label>
                  <select
                    value={selectedSectionFilter}
                    onChange={e => setSelectedSectionFilter(e.target.value)}
                    style={{ minWidth: 200 }}
                  >
                    <option value="all">Toutes les sections ({groupes.length} groupes)</option>
                    {SECTIONS.map(s => (
                      <option key={s.id} value={s.id}>{s.short}</option>
                    ))}
                  </select>
                </div>

                {/* Search input */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input
                    type="text"
                    placeholder="Filtrer un groupe (ex: FS201)..."
                    value={searchGroupe}
                    onChange={e => setSearchGroupe(e.target.value)}
                    style={{ width: 190 }}
                  />
                </div>

                <div style={{ flex: 1 }} />

                {/* Action buttons */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {role === 'admin' && (
                    <>
                      <button
                        className="btn btn-primary"
                        onClick={handleGenerate}
                        disabled={loadingGen || !selectedSemaine}
                        title="Générer automatiquement cette semaine"
                      >
                        {loadingGen ? 'Génération en cours…' : 'Générer l\'emploi'}
                      </button>
                      <button
                        className="btn btn-success"
                        onClick={handleValider}
                        disabled={!selectedSemaine}
                        title="Valider toutes les séances de cette semaine"
                      >
                        Valider la semaine
                      </button>
                      <button
                        className="btn btn-ghost"
                        onClick={handleVider}
                        disabled={!selectedSemaine}
                        title="Effacer les séances non verrouillées de cette semaine"
                        style={{ color: '#dc2626' }}
                      >
                        Vider la semaine
                      </button>
                      <button
                        className="btn btn-warning"
                        onClick={() => setOpenSelectModify(true)}
                        title="Sélectionner et modifier une séance existante"
                      >
                        Modifier une séance
                      </button>
                      <button
                        className="btn btn-primary"
                        onClick={handleAddDirect}
                        title="Ajouter manuellement une nouvelle séance"
                      >
                        Ajouter une séance
                      </button>
                    </>
                  )}
                  <button
                    className="btn btn-ghost"
                    onClick={handleExportCSV}
                    title="Télécharger l'emploi du temps sous format Excel / CSV"
                  >
                    Exporter CSV
                  </button>
                  <button
                    className="btn btn-ghost"
                    onClick={() => window.print()}
                    title="Imprimer l'emploi du temps au format officiel"
                  >
                    Imprimer
                  </button>
                </div>
              </div>

              {/* ── Official Header ── */}
              <div style={{ textAlign: 'center', margin: '16px 0 12px' }}>
                <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#0f2d5e' }}>
                  Emploi du temps - NTIC2
                </h2>
                {selectedSemaine && (
                  <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 13 }}>
                    Semaine {selectedSemaine.numero} : du {formatDate(selectedSemaine.date_debut)} au {formatDate(selectedSemaine.date_fin)}
                    {' · '}
                    <strong>{seances.length}</strong> séances planifiées
                    {' · '}
                    <span style={{ color: '#16a34a' }}>{seances.filter(s => s.statut === 'valide').length} validées</span>
                    {' · '}
                    <span style={{ color: '#d97706' }}>{seances.filter(s => s.statut === 'brouillon').length} brouillon</span>
                  </p>
                )}
              </div>

              {/* ── Notice Admin Edit ── */}
              <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6, padding: '10px 16px', margin: '14px 0 8px', fontSize: 12.5, color: '#1e40af', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>
                  <strong>Modification directe :</strong> Cliquez sur n'importe quelle séance du tableau pour la modifier (Formateur, Module, Salle, Créneau, Statut) ou cliquez sur une case vide pour ajouter une nouvelle séance.
                </span>
              </div>

              {/* ── THE EXACT NTIC2 TABLE ── */}
              {loadingSeances ? (
                <div className="loading-state">
                  Chargement de l'emploi du temps de la semaine {selectedSemaine?.numero}…
                </div>
              ) : groupedSections.length === 0 ? (
                <div className="empty-state">
                  <h3>Aucun groupe trouvé</h3>
                  <p>Essayez de modifier vos filtres de recherche ou de section.</p>
                </div>
              ) : (
                <div className="table-container">
                  <table className="ntic-table">
                    <thead>
                      <tr>
                        <th rowSpan={3}>Groupe</th>
                        <th rowSpan={3}>Information</th>
                        <th colSpan={4}>Lundi</th>
                        <th colSpan={4}>Mardi</th>
                        <th colSpan={4}>Mercredi</th>
                        <th colSpan={4}>Jeudi</th>
                        <th colSpan={4}>Vendredi</th>
                        <th colSpan={4}>Samedi</th>
                        <th rowSpan={3}>Effectif</th>
                      </tr>

                      <tr>
                        <th>SEANCE 1</th>
                        <th>SEANCE 2</th>
                        <th>SEANCE 3</th>
                        <th>SEANCE 4</th>

                        <th>SEANCE 1</th>
                        <th>SEANCE 2</th>
                        <th>SEANCE 3</th>
                        <th>SEANCE 4</th>

                        <th>SEANCE 1</th>
                        <th>SEANCE 2</th>
                        <th>SEANCE 3</th>
                        <th>SEANCE 4</th>

                        <th>SEANCE 1</th>
                        <th>SEANCE 2</th>
                        <th>SEANCE 3</th>
                        <th>SEANCE 4</th>

                        <th>SEANCE 1</th>
                        <th>SEANCE 2</th>
                        <th>SEANCE 3</th>
                        <th>SEANCE 4</th>

                        <th>SEANCE 1</th>
                        <th>SEANCE 2</th>
                        <th>SEANCE 3</th>
                        <th>SEANCE 4</th>
                      </tr>

                      <tr className="horaire">
                        {/* Lundi: 08h00-13h00 matin, 13h30-18h30 après-midi */}
                        <th>08h00-10h30</th>
                        <th>10h30-13h00</th>
                        <th>13h30-16h00</th>
                        <th>16h00-18h30</th>

                        {/* Mardi */}
                        <th>08h00-10h30</th>
                        <th>10h30-13h00</th>
                        <th>13h30-16h00</th>
                        <th>16h00-18h30</th>

                        {/* Mercredi */}
                        <th>08h00-10h30</th>
                        <th>10h30-13h00</th>
                        <th>13h30-16h00</th>
                        <th>16h00-18h30</th>

                        {/* Jeudi */}
                        <th>08h00-10h30</th>
                        <th>10h30-13h00</th>
                        <th>13h30-16h00</th>
                        <th>16h00-18h30</th>

                        {/* Vendredi: 08h00-12h30 matin, 14h30-18h30 après-midi */}
                        <th>08h00-10h30</th>
                        <th>10h30-12h30</th>
                        <th>14h30-16h30</th>
                        <th>16h30-18h30</th>

                        {/* Samedi */}
                        <th>08h00-10h30</th>
                        <th>10h30-13h00</th>
                        <th>13h30-16h00</th>
                        <th>16h00-18h30</th>
                      </tr>
                    </thead>

                    <tbody>
                      {groupedSections.map(section => (
                        <Fragment key={section.id}>
                          {/* ── Section Title Banner (e.g. DEV 1ÈRE ANNÉE, DEV 2ÈME ANNÉE) ── */}
                          <tr className="section-divider-row">
                            <td colSpan={27} className="section-divider-cell">
                              {section.title}
                            </td>
                          </tr>

                          {section.groupes.map(groupe => {
                            const displayCode = formatGroupeDisplay(groupe.code)

                            return (
                              <Fragment key={groupe.id}>
                                {/* ROW 1: FORMATEUR */}
                                <tr>
                                  <td rowSpan={3} className="groupe">{displayCode}</td>
                                  <td className="type">FORMATEUR</td>

                                  {ALL_24_SLOTS.map(slot => {
                                    const s = seanceMap[`${groupe.id}_${slot.jour}_${slot.seance}`]
                                    const profLabel = s ? formatProfDisplay(s.professeurs) : ''

                                    return (
                                      <td
                                        key={`prof_${groupe.id}_${slot.jour}_${slot.seance}`}
                                        className={s ? 'cell-clickable' : 'vide cell-clickable'}
                                        onClick={() => s ? setEditSeance(s) : handleCellClickEmpty(groupe, slot.jour, slot.seance)}
                                        title={s
                                          ? `${s.module_intitule} | Formateur: ${s.professeurs?.map(p => p.prof_nom).join(', ') || '—'} | Salle: ${s.salle_nom || (s.mode === 'distance' ? 'TEAM' : '—')} | Cliquez pour modifier`
                                          : `Cliquer pour ajouter une séance (${displayCode} - ${slot.jourNom} S${slot.seance})`
                                        }
                                      >
                                        {profLabel}
                                      </td>
                                    )
                                  })}

                                  <td rowSpan={3} className="effectif">{groupe.effectif || 25}</td>
                                </tr>

                                {/* ROW 2: MODULE */}
                                <tr>
                                  <td className="type">MODULE</td>

                                  {ALL_24_SLOTS.map(slot => {
                                    const s = seanceMap[`${groupe.id}_${slot.jour}_${slot.seance}`]

                                    return (
                                      <td
                                        key={`mod_${groupe.id}_${slot.jour}_${slot.seance}`}
                                        className={s ? 'module cell-clickable' : 'vide cell-clickable'}
                                        onClick={() => s ? setEditSeance(s) : handleCellClickEmpty(groupe, slot.jour, slot.seance)}
                                        title={s ? `${s.module_intitule} (${s.module_code}) | Cliquez pour modifier` : `Cliquer pour ajouter une séance (${displayCode} - ${slot.jourNom} S${slot.seance})`}
                                      >
                                        {s ? (s.module_intitule || s.module_code) : ''}
                                      </td>
                                    )
                                  })}
                                </tr>

                                {/* ROW 3: SALLE */}
                                <tr>
                                  <td className="type">SALLE</td>

                                  {ALL_24_SLOTS.map(slot => {
                                    const s = seanceMap[`${groupe.id}_${slot.jour}_${slot.seance}`]
                                    const salleLabel = s ? (s.salle_nom || (s.mode === 'distance' ? 'TEAM' : '—')) : ''

                                    return (
                                      <td
                                        key={`sal_${groupe.id}_${slot.jour}_${slot.seance}`}
                                        className={s ? 'cell-clickable' : 'vide cell-clickable'}
                                        onClick={() => s ? setEditSeance(s) : handleCellClickEmpty(groupe, slot.jour, slot.seance)}
                                        title={s ? `Salle: ${salleLabel} | Cliquez pour modifier` : `Cliquer pour ajouter une séance (${displayCode} - ${slot.jourNom} S${slot.seance})`}
                                      >
                                        {salleLabel}
                                      </td>
                                    )
                                  })}
                                </tr>
                              </Fragment>
                            )
                          })}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* ── GROUPES VIEW ── */}
          {activeNav === 'groupes' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Header card */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                padding: '20px 24px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 16
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <h2 style={{ margin: 0, fontSize: 20, color: '#0f2d5e', fontWeight: 700 }}>
                      Gestion des Groupes
                    </h2>
                    <span style={{
                      background: '#eff6ff',
                      color: '#1a5fa8',
                      fontSize: 12,
                      fontWeight: 700,
                      padding: '3px 10px',
                      borderRadius: 20,
                      border: '1px solid #bfdbfe'
                    }}>
                      {groupes.length} groupes
                    </span>
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                    Effectif total : <strong>{groupes.reduce((a, g) => a + (g.effectif || 0), 0)}</strong> stagiaires • Structure pédagogique de l'établissement
                  </p>
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setEditingGroupe(null)
                    setGroupeModalOpen(true)
                  }}
                  style={{ padding: '0 20px', height: 40, fontSize: 13, boxShadow: '0 2px 6px rgba(26,95,168,0.25)' }}
                >
                  + Ajouter un Groupe
                </button>
              </div>

              {/* Filters toolbar */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                padding: '16px 20px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                flexWrap: 'wrap'
              }}>
                <div style={{ flex: '1 1 240px', minWidth: 200 }}>
                  <input
                    type="text"
                    placeholder="Rechercher un groupe (ex: DEV101, TSM, Full Stack...)"
                    value={groupeSearch}
                    onChange={e => setGroupeSearch(e.target.value)}
                    style={{
                      width: '100%',
                      height: 38,
                      padding: '0 12px',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: 8,
                      fontSize: 13,
                      outline: 'none',
                      background: '#f8fafc'
                    }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>Filière :</label>
                  <select
                    value={groupeFiliereFilter}
                    onChange={e => setGroupeFiliereFilter(e.target.value)}
                    style={{
                      height: 38,
                      padding: '0 12px',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: 8,
                      fontSize: 13,
                      background: '#fff',
                      outline: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="all">Toutes les filières</option>
                    {filieres.map(f => (
                      <option key={f.id} value={f.id}>{f.intitule} ({f.code})</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>Année :</label>
                  <select
                    value={groupeAnneeFilter}
                    onChange={e => setGroupeAnneeFilter(e.target.value)}
                    style={{
                      height: 38,
                      padding: '0 12px',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: 8,
                      fontSize: 13,
                      background: '#fff',
                      outline: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="all">Toutes les années</option>
                    <option value="1">1ère Année</option>
                    <option value="2">2ème Année</option>
                    <option value="3">3ème Année</option>
                  </select>
                </div>

                {(groupeSearch || groupeFiliereFilter !== 'all' || groupeAnneeFilter !== 'all') && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setGroupeSearch('')
                      setGroupeFiliereFilter('all')
                      setGroupeAnneeFilter('all')
                    }}
                    style={{ height: 38, padding: '0 12px', fontSize: 12 }}
                  >
                    Réinitialiser les filtres
                  </button>
                )}

                <div style={{ marginLeft: 'auto', fontSize: 12, color: '#64748b' }}>
                  Affichage de <strong>{filteredGroupesList.length}</strong> sur {groupes.length} groupes
                </div>
              </div>

              {/* Table Card */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                overflow: 'hidden'
              }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                        <th style={{ padding: '14px 18px' }}>Code Affiché</th>
                        <th style={{ padding: '14px 18px' }}>Code BDD</th>
                        <th style={{ padding: '14px 18px' }}>Filière</th>
                        <th style={{ padding: '14px 18px', textAlign: 'center' }}>Année</th>
                        <th style={{ padding: '14px 18px', textAlign: 'center' }}>Effectif</th>
                        <th style={{ padding: '14px 18px' }}>Mode</th>
                        <th style={{ padding: '14px 18px' }}>Régime</th>
                        <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredGroupesList.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ padding: 48, textAlign: 'center', color: '#94a3b8' }}>
                            
                            <div style={{ fontWeight: 600, fontSize: 15, color: '#475569' }}>Aucun groupe trouvé</div>
                            <div style={{ fontSize: 13, marginTop: 4 }}>Essayez de modifier vos critères de recherche</div>
                          </td>
                        </tr>
                      ) : (
                        filteredGroupesList.map(g => (
                          <tr
                            key={g.id}
                            style={{
                              borderBottom: '1px solid #f1f5f9',
                              transition: 'background 0.15s'
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                          >
                            <td style={{ padding: '14px 18px', fontWeight: 700, color: '#1e3a8a' }}>
                              <span style={{
                                background: '#eff6ff',
                                color: '#1e40af',
                                padding: '4px 10px',
                                borderRadius: 6,
                                border: '1px solid #bfdbfe'
                              }}>
                                {formatGroupeDisplay(g.code)}
                              </span>
                            </td>
                            <td style={{ padding: '14px 18px', fontWeight: 600, color: '#334155' }}>
                              {g.code}
                            </td>
                            <td style={{ padding: '14px 18px' }}>
                              <div style={{ fontWeight: 600, color: '#0f172a' }}>{g.filiere_nom}</div>
                              <div style={{ fontSize: 11, color: '#64748b' }}>{g.filiere_code}</div>
                            </td>
                            <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                              <span style={{
                                background: g.annee_etude === 1 ? '#f0fdf4' : (g.annee_etude === 2 ? '#eff6ff' : '#fdf4ff'),
                                color: g.annee_etude === 1 ? '#15803d' : (g.annee_etude === 2 ? '#1d4ed8' : '#86198f'),
                                padding: '3px 8px',
                                borderRadius: 6,
                                fontSize: 12,
                                fontWeight: 600
                              }}>
                                {g.annee_etude}ère / ème
                              </span>
                            </td>
                            <td style={{ padding: '14px 18px', textAlign: 'center', fontWeight: 700, color: '#0f172a' }}>
                              {g.effectif}
                            </td>
                            <td style={{ padding: '14px 18px', color: '#475569' }}>
                              {g.mode_formation || 'Résidentiel'}
                            </td>
                            <td style={{ padding: '14px 18px', color: '#64748b', fontSize: 12 }}>
                              <span style={{ background: '#f1f5f9', padding: '2px 6px', borderRadius: 4 }}>
                                {g.regime || 'CDJ'}
                              </span>
                            </td>
                            <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                              <div style={{ display: 'inline-flex', gap: 6 }}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditingGroupe(g)
                                    setGroupeModalOpen(true)
                                  }}
                                  title="Modifier le groupe"
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: 6,
                                    border: '1px solid #bfdbfe',
                                    background: '#eff6ff',
                                    color: '#1d4ed8',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4,
                                    transition: 'all 0.15s'
                                  }}
                                  onMouseEnter={e => {
                                    e.currentTarget.style.background = '#dbeafe'
                                  }}
                                  onMouseLeave={e => {
                                    e.currentTarget.style.background = '#eff6ff'
                                  }}
                                >
                                  Modifier
                                </button>

                                <button
                                  type="button"
                                  onClick={() => setDeletingGroupe(g)}
                                  title="Supprimer le groupe"
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: 6,
                                    border: '1px solid #fecaca',
                                    background: '#fef2f2',
                                    color: '#b91c1c',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4,
                                    transition: 'all 0.15s'
                                  }}
                                  onMouseEnter={e => {
                                    e.currentTarget.style.background = '#fee2e2'
                                  }}
                                  onMouseLeave={e => {
                                    e.currentTarget.style.background = '#fef2f2'
                                  }}
                                >
                                  Supprimer
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ── FORMATEURS VIEW ── */}
          {activeNav === 'profs' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Header card */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                padding: '20px 24px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 16
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <h2 style={{ margin: 0, fontSize: 20, color: '#0f2d5e', fontWeight: 700 }}>
                      Gestion des Formateurs
                    </h2>
                    <span style={{
                      background: '#f0fdf4',
                      color: '#15803d',
                      fontSize: 12,
                      fontWeight: 700,
                      padding: '3px 10px',
                      borderRadius: 20,
                      border: '1px solid #bbf7d0'
                    }}>
                      {professeurs.length} formateurs
                    </span>
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                    Corps professoral de l'établissement • Gestion des affectations et disponibilités
                  </p>
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setEditingProf(null)
                    setProfModalOpen(true)
                  }}
                  style={{ padding: '0 20px', height: 40, fontSize: 13, boxShadow: '0 2px 6px rgba(26,95,168,0.25)' }}
                >
                  + Ajouter un Formateur
                </button>
              </div>

              {/* Filters toolbar */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                padding: '16px 20px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                flexWrap: 'wrap'
              }}>
                <div style={{ flex: '1 1 260px', minWidth: 200 }}>
                  <input
                    type="text"
                    placeholder="Rechercher un formateur (nom, matricule, email...)"
                    value={profSearch}
                    onChange={e => setProfSearch(e.target.value)}
                    style={{
                      width: '100%',
                      height: 38,
                      padding: '0 12px',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: 8,
                      fontSize: 13,
                      outline: 'none',
                      background: '#f8fafc'
                    }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>Statut :</label>
                  <select
                    value={profStatutFilter}
                    onChange={e => setProfStatutFilter(e.target.value)}
                    style={{
                      height: 38,
                      padding: '0 12px',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: 8,
                      fontSize: 13,
                      background: '#fff',
                      outline: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="all">Tous les statuts</option>
                    <option value="permanent">Permanent</option>
                    <option value="vacataire">Vacataire</option>
                  </select>
                </div>

                {(profSearch || profStatutFilter !== 'all') && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setProfSearch('')
                      setProfStatutFilter('all')
                    }}
                    style={{ height: 38, padding: '0 12px', fontSize: 12 }}
                  >
                    Réinitialiser
                  </button>
                )}

                <div style={{ marginLeft: 'auto', fontSize: 12, color: '#64748b' }}>
                  Affichage de <strong>{filteredProfsList.length}</strong> sur {professeurs.length} formateurs
                </div>
              </div>

              {/* Table Card */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                overflow: 'hidden'
              }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                        <th style={{ padding: '14px 18px' }}>Nom Complet</th>
                        <th style={{ padding: '14px 18px' }}>Nom Affiché (Emploi)</th>
                        <th style={{ padding: '14px 18px' }}>Matricule</th>
                        <th style={{ padding: '14px 18px' }}>Email</th>
                        <th style={{ padding: '14px 18px', textAlign: 'center' }}>Statut</th>
                        <th style={{ padding: '14px 18px', textAlign: 'center' }}>Présence</th>
                        <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProfsList.length === 0 ? (
                        <tr>
                          <td colSpan={7} style={{ padding: 48, textAlign: 'center', color: '#94a3b8' }}>
                            
                            <div style={{ fontWeight: 600, fontSize: 15, color: '#475569' }}>Aucun formateur trouvé</div>
                            <div style={{ fontSize: 13, marginTop: 4 }}>Modifiez votre filtre ou terme de recherche</div>
                          </td>
                        </tr>
                      ) : (
                        filteredProfsList.map(p => (
                          <tr
                            key={p.id}
                            style={{
                              borderBottom: '1px solid #f1f5f9',
                              transition: 'background 0.15s'
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                          >
                            <td style={{ padding: '14px 18px', fontWeight: 600, color: '#0f172a' }}>
                              {p.nom_complet}
                            </td>
                            <td style={{ padding: '14px 18px', fontWeight: 700, color: '#1e3a8a' }}>
                              <span style={{
                                background: '#eff6ff',
                                color: '#1e40af',
                                padding: '3px 8px',
                                borderRadius: 6,
                                border: '1px solid #bfdbfe',
                                fontSize: 12
                              }}>
                                {formatProfDisplay([{ prof_nom: p.nom_complet }])}
                              </span>
                            </td>
                            <td style={{ padding: '14px 18px', color: '#64748b', fontFamily: 'monospace' }}>
                              {p.matricule || '—'}
                            </td>
                            <td style={{ padding: '14px 18px', color: '#475569' }}>
                              {p.email || '—'}
                            </td>
                            <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                              <span style={{
                                background: p.statut === 'vacataire' ? '#eff6ff' : '#f0fdf4',
                                color: p.statut === 'vacataire' ? '#1d4ed8' : '#15803d',
                                padding: '3px 8px',
                                borderRadius: 4,
                                fontSize: 11,
                                fontWeight: 600,
                                textTransform: 'capitalize'
                              }}>
                                {p.statut || 'Permanent'}
                              </span>
                            </td>
                            <td style={{ padding: '14px 18px', textAlign: 'center', fontWeight: 600, color: '#334155' }}>
                              {p.taux_presence ? `${p.taux_presence}%` : '100%'}
                            </td>
                            <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                              <div style={{ display: 'inline-flex', gap: 6 }}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditingProf(p)
                                    setProfModalOpen(true)
                                  }}
                                  title="Modifier le formateur"
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: 6,
                                    border: '1px solid #bfdbfe',
                                    background: '#eff6ff',
                                    color: '#1d4ed8',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4
                                  }}
                                  onMouseEnter={e => e.currentTarget.style.background = '#dbeafe'}
                                  onMouseLeave={e => e.currentTarget.style.background = '#eff6ff'}
                                >
                                  Modifier
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setDeletingProf(p)}
                                  title="Supprimer le formateur"
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: 6,
                                    border: '1px solid #fecaca',
                                    background: '#fef2f2',
                                    color: '#b91c1c',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4
                                  }}
                                  onMouseEnter={e => e.currentTarget.style.background = '#fee2e2'}
                                  onMouseLeave={e => e.currentTarget.style.background = '#fef2f2'}
                                >
                                  Supprimer
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ── SALLES VIEW ── */}
          {activeNav === 'salles' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Header card */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                padding: '20px 24px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 16
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <h2 style={{ margin: 0, fontSize: 20, color: '#0f2d5e', fontWeight: 700 }}>
                      Gestion des Salles et Locaux
                    </h2>
                    <span style={{
                      background: '#fef3c7',
                      color: '#b45309',
                      fontSize: 12,
                      fontWeight: 700,
                      padding: '3px 10px',
                      borderRadius: 20,
                      border: '1px solid #fde68a'
                    }}>
                      {salles.length} salles
                    </span>
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                    Capacité d'accueil globale : <strong>{salles.reduce((a, s) => a + (s.capacite || 30), 0)}</strong> places • Salles de cours, spécialisées et laboratoires
                  </p>
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setEditingSalle(null)
                    setSalleModalOpen(true)
                  }}
                  style={{ padding: '0 20px', height: 40, fontSize: 13, boxShadow: '0 2px 6px rgba(26,95,168,0.25)' }}
                >
                  + Ajouter une Salle
                </button>
              </div>

              {/* Filters toolbar */}
              <div style={{
                background: '#fff',
                borderRadius: 12,
                padding: '16px 20px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                flexWrap: 'wrap'
              }}>
                <div style={{ flex: '1 1 240px', minWidth: 200 }}>
                  <input
                    type="text"
                    placeholder="Rechercher une salle (ex: SC1, SP2, LABO...)"
                    value={salleSearch}
                    onChange={e => setSalleSearch(e.target.value)}
                    style={{
                      width: '100%',
                      height: 38,
                      padding: '0 12px',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: 8,
                      fontSize: 13,
                      outline: 'none',
                      background: '#f8fafc'
                    }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>Type de Salle :</label>
                  <select
                    value={salleTypeFilter}
                    onChange={e => setSalleTypeFilter(e.target.value)}
                    style={{
                      height: 38,
                      padding: '0 12px',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: 8,
                      fontSize: 13,
                      background: '#fff',
                      outline: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="all">Tous les types</option>
                    {typesSalles?.map(t => (
                      <option key={t.id} value={t.id}>{t.libelle} ({t.code})</option>
                    ))}
                  </select>
                </div>

                {(salleSearch || salleTypeFilter !== 'all') && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setSalleSearch('')
                      setSalleTypeFilter('all')
                    }}
                    style={{ height: 38, padding: '0 12px', fontSize: 12 }}
                  >
                    Réinitialiser
                  </button>
                )}

                <div style={{ marginLeft: 'auto', fontSize: 12, color: '#64748b' }}>
                  Affichage de <strong>{filteredSallesList.length}</strong> sur {salles.length} salles
                </div>
              </div>

              {/* Salles Grid of Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
                {filteredSallesList.length === 0 ? (
                  <div style={{ gridColumn: '1 / -1', background: '#fff', borderRadius: 12, padding: 48, textAlign: 'center', color: '#94a3b8', border: '1px solid #e2e8f0' }}>
                    
                    <div style={{ fontWeight: 600, fontSize: 15, color: '#475569' }}>Aucune salle trouvée</div>
                    <div style={{ fontSize: 13, marginTop: 4 }}>Modifiez votre filtre ou terme de recherche</div>
                  </div>
                ) : (
                  filteredSallesList.map(s => {
                    const isLabo = s.type_code === 'LABO'
                    const isSP = s.type_code === 'SP'
                    const badgeBg = isLabo ? '#fdf4ff' : (isSP ? '#eff6ff' : '#f0fdf4')
                    const badgeColor = isLabo ? '#86198f' : (isSP ? '#1d4ed8' : '#15803d')

                    return (
                      <div
                        key={s.id}
                        style={{
                          background: '#fff',
                          borderRadius: 12,
                          border: '1px solid #e2e8f0',
                          padding: 18,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          gap: 14,
                          transition: 'transform 0.15s, box-shadow 0.15s'
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.transform = 'translateY(-2px)'
                          e.currentTarget.style.boxShadow = '0 6px 14px rgba(0,0,0,0.08)'
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.transform = 'translateY(0)'
                          e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)'
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              
                              <div>
                                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#0f2d5e' }}>{s.nom}</h3>
                                <span style={{ fontSize: 12, color: '#64748b' }}>Salle {s.nom}</span>
                              </div>
                            </div>
                            <span style={{
                              background: badgeBg,
                              color: badgeColor,
                              padding: '3px 8px',
                              borderRadius: 6,
                              fontSize: 11,
                              fontWeight: 700
                            }}>
                              {s.type_code}
                            </span>
                          </div>

                          <div style={{ marginTop: 14, background: '#f8fafc', padding: 10, borderRadius: 8, fontSize: 12, color: '#475569', display: 'flex', justifyContent: 'space-between' }}>
                            <span>Type : <strong>{s.type_libelle}</strong></span>
                            <span>Capacité : <strong>{s.capacite || 30} pl.</strong></span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, borderTop: '1px solid #f1f5f9', paddingTop: 12 }}>
                          <button
                            type="button"
                            onClick={() => {
                              setEditingSalle(s)
                              setSalleModalOpen(true)
                            }}
                            title="Modifier la salle"
                            style={{
                              padding: '6px 12px',
                              borderRadius: 6,
                              border: '1px solid #bfdbfe',
                              background: '#eff6ff',
                              color: '#1d4ed8',
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = '#dbeafe'}
                            onMouseLeave={e => e.currentTarget.style.background = '#eff6ff'}
                          >
                            Modifier
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeletingSalle(s)}
                            title="Supprimer la salle"
                            style={{
                              padding: '6px 12px',
                              borderRadius: 6,
                              border: '1px solid #fecaca',
                              background: '#fef2f2',
                              color: '#b91c1c',
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = '#fee2e2'}
                            onMouseLeave={e => e.currentTarget.style.background = '#fef2f2'}
                          >
                            Supprimer
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ── Modals ── */}
      {editSeance && (
        <EditModal
          seance={editSeance}
          unites={unites}
          salles={salles}
          creneaux={creneaux}
          professeurs={professeurs}
          onClose={() => setEditSeance(null)}
          onSave={() => {
            setEditSeance(null)
            addToast('Séance mise à jour avec succès', 'success')
            refreshSeances()
          }}
          onDelete={handleDelete}
        />
      )}

      {addPrefill && (
        <AddModal
          prefill={addPrefill}
          semaine={selectedSemaine}
          unites={unites}
          salles={salles}
          creneaux={creneaux}
          professeurs={professeurs}
          groupes={groupes}
          onClose={() => setAddPrefill(null)}
          onSave={() => {
            setAddPrefill(null)
            addToast('Nouvelle séance créée avec succès', 'success')
            refreshSeances()
          }}
        />
      )}

      {openSelectModify && (
        <SelectModifyModal
          seances={seances}
          groupes={groupes}
          onClose={() => setOpenSelectModify(false)}
          onSelectSeance={s => setEditSeance(s)}
        />
      )}

      {groupeModalOpen && (
        <GroupeModal
          groupe={editingGroupe}
          filieres={filieres}
          onClose={() => {
            setGroupeModalOpen(false)
            setEditingGroupe(null)
          }}
          onSave={handleSaveGroupe}
        />
      )}

      {deletingGroupe && (
        <DeleteGroupeModal
          groupe={deletingGroupe}
          loading={deletingLoading}
          onClose={() => setDeletingGroupe(null)}
          onConfirm={handleDeleteGroupeConfirm}
        />
      )}

      {profModalOpen && (
        <ProfesseurModal
          prof={editingProf}
          onClose={() => {
            setProfModalOpen(false)
            setEditingProf(null)
          }}
          onSave={handleSaveProf}
        />
      )}

      {deletingProf && (
        <DeleteProfesseurModal
          prof={deletingProf}
          loading={deletingProfLoading}
          onClose={() => setDeletingProf(null)}
          onConfirm={handleDeleteProfConfirm}
        />
      )}

      {salleModalOpen && (
        <SalleModal
          salle={editingSalle}
          typesSalles={typesSalles}
          onClose={() => {
            setSalleModalOpen(false)
            setEditingSalle(null)
          }}
          onSave={handleSaveSalle}
        />
      )}

      {deletingSalle && (
        <DeleteSalleModal
          salle={deletingSalle}
          loading={deletingSalleLoading}
          onClose={() => setDeletingSalle(null)}
          onConfirm={handleDeleteSalleConfirm}
        />
      )}
    </div>
  )
}
