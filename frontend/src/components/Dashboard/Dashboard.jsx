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

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard({ role = 'admin', onLogout }) {
  const [activeNav, setActiveNav] = useState('emploi')
  const [semaines, setSemaines] = useState([])
  const [selectedSemaine, setSelectedSemaine] = useState(null)
  const [seances, setSeances] = useState([])
  const [groupes, setGroupes] = useState([])
  const [professeurs, setProfesseurs] = useState([])
  const [salles, setSalles] = useState([])
  const [creneaux, setCreneaux] = useState([])
  const [unites, setUnites] = useState([])
  const [stats, setStats] = useState(null)

  // Filters
  const [selectedSectionFilter, setSelectedSectionFilter] = useState('all')
  const [searchGroupe, setSearchGroupe] = useState('')

  // State flags
  const [loadingSeances, setLoadingSeances] = useState(false)
  const [loadingGen, setLoadingGen] = useState(false)
  const [editSeance, setEditSeance] = useState(null)
  const [openSelectModify, setOpenSelectModify] = useState(false)
  const [addPrefill, setAddPrefill] = useState(null)
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
        const [sw, g, p, sl, cr, u, hc] = await Promise.all([
          apiFetch(`${API}/semaines`),
          apiFetch(`${API}/groupes`),
          apiFetch(`${API}/professeurs`),
          apiFetch(`${API}/salles`),
          apiFetch(`${API}/creneaux`),
          apiFetch(`${API}/unites`).catch(() => []),
          apiFetch(`${API}/health`),
        ])
        setSemaines(sw)
        setGroupes(g)
        setProfesseurs(p)
        setSalles(sl)
        setCreneaux(cr)
        setUnites(u)
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
            <div style={{ background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h3 style={{ margin: 0, fontSize: 18, color: '#0f2d5e' }}>Liste des Groupes ({groupes.length})</h3>
                <span style={{ fontSize: 13, color: '#64748b' }}>Effectif total : {groupes.reduce((a, g) => a + (g.effectif || 0), 0)} stagiaires</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                      <th style={{ padding: '12px 16px' }}>Code Affiché</th>
                      <th style={{ padding: '12px 16px' }}>Code BDD</th>
                      <th style={{ padding: '12px 16px' }}>Filière</th>
                      <th style={{ padding: '12px 16px' }}>Année</th>
                      <th style={{ padding: '12px 16px' }}>Effectif</th>
                      <th style={{ padding: '12px 16px' }}>Mode</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupes.map(g => (
                      <tr key={g.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#1e3a8a' }}>{formatGroupeDisplay(g.code)}</td>
                        <td style={{ padding: '12px 16px', color: '#64748b' }}>{g.code}</td>
                        <td style={{ padding: '12px 16px' }}>{g.filiere_nom} ({g.filiere_code})</td>
                        <td style={{ padding: '12px 16px' }}>{g.annee_etude}ère / ème année</td>
                        <td style={{ padding: '12px 16px', fontWeight: 600 }}>{g.effectif}</td>
                        <td style={{ padding: '12px 16px' }}>{g.mode_formation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── FORMATEURS VIEW ── */}
          {activeNav === 'profs' && (
            <div style={{ background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h3 style={{ margin: 0, fontSize: 18, color: '#0f2d5e' }}>Formateurs de l'Établissement ({professeurs.length})</h3>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                      <th style={{ padding: '12px 16px' }}>Nom Complet</th>
                      <th style={{ padding: '12px 16px' }}>Nom Affiché (Tableau)</th>
                      <th style={{ padding: '12px 16px' }}>Email</th>
                      <th style={{ padding: '12px 16px' }}>Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {professeurs.map(p => (
                      <tr key={p.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 16px', fontWeight: 600, color: '#0f172a' }}>{p.nom_complet}</td>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#1e3a8a' }}>{formatProfDisplay([{ prof_nom: p.nom_complet }])}</td>
                        <td style={{ padding: '12px 16px', color: '#64748b' }}>{p.email || '—'}</td>
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{ background: '#f1f5f9', color: '#334155', padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                            Actif
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── SALLES VIEW ── */}
          {activeNav === 'salles' && (
            <div style={{ background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h3 style={{ margin: 0, fontSize: 18, color: '#0f2d5e' }}>Salles et Locaux ({salles.length})</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
                {salles.map(s => (
                  <div key={s.id} style={{ border: '1px solid #cbd5e1', borderRadius: 8, padding: 16, background: '#f8fafc' }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: '#0f2d5e' }}>{s.nom}</div>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>Type: {s.type_libelle} ({s.type_code})</div>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>Capacité: {s.capacite || 30} places</div>
                  </div>
                ))}
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
    </div>
  )
}
