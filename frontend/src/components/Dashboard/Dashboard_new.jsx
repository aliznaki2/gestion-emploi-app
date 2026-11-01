import { useState, useEffect, useCallback } from 'react'
import './Dashboard.css'

const API = 'http://localhost:3001/api'

const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
const SEANCES = [
  { num: 1, debut: '08:00', fin: '10:30' },
  { num: 2, debut: '10:30', fin: '13:00' },
  { num: 3, debut: '13:30', fin: '16:00' },
  { num: 4, debut: '16:00', fin: '18:30' },
]

const formatDate = d => d ? new Date(d).toLocaleDateString('fr-MA', { day: '2-digit', month: 'short', year: 'numeric' }) : ''
const formatShort = d => d ? new Date(d).toLocaleDateString('fr-MA', { day: '2-digit', month: 'short' }) : ''
const apiFetch = async (url, opts = {}) => {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!r.ok) {
    let message = 'Erreur serveur'
    try {
      const e = await r.json()
      message = e.message || e.error || e.detail || message
    } catch {}
    throw new Error(message)
  }
  return r.json()
}

function ToastContainer({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>{t.message}</div>
      ))}
    </div>
  )
}

function CellContent({ seance, onEdit, onDelete }) {
  if (!seance) return <div className="cell-empty"></div>
  const prof = seance.professeurs?.[0]?.prof_nom || ''
  const profShort = prof.split(' ').pop() || prof
  return (
    <div className={`cell-seance type-${seance.type_module || 'technique'} statut-${seance.statut}`}>
      <div className="cell-module">{seance.module_code}</div>
      <div className="cell-salle">{seance.salle_nom || 'Dist.'}</div>
      <div className="cell-prof">{profShort}</div>
      {(onEdit || onDelete) && !seance.verrouillee && (
        <div className="cell-actions">
          {onEdit && <button onClick={e => { e.stopPropagation(); onEdit(seance) }} title="Modifier">✏</button>}
          {onDelete && <button onClick={e => { e.stopPropagation(); onDelete(seance) }} title="Supprimer">✕</button>}
        </div>
      )}
    </div>
  )
}

function TimetableGrid({ seances, semaine, groupes, filterFiliere, onEdit, onDelete }) {
  if (!semaine) return (
    <div className="empty-state">
      <div className="empty-icon">📅</div>
      <h3>Selectionnez une semaine</h3>
    </div>
  )
  if (seances.length === 0) return (
    <div className="empty-state">
      <div className="empty-icon">📋</div>
      <h3>Aucune seance pour cette semaine</h3>
      <p>Cliquez sur Generer pour creer l emploi du temps</p>
    </div>
  )

  const displayGroups = filterFiliere === 'all'
    ? groupes
    : groupes.filter(g => g.filiere_code === filterFiliere)

  const lookup = {}
  for (const s of seances) {
    for (const g of (s.groupes || [])) {
      const gc = g.groupe_code
      if (!lookup[gc]) lookup[gc] = {}
      if (!lookup[gc][s.jour]) lookup[gc][s.jour] = {}
      if (!lookup[gc][s.jour][s.numero_seance]) lookup[gc][s.jour][s.numero_seance] = s
    }
  }

  const dayDate = (i) => {
    if (!semaine.date_debut) return ''
    const d = new Date(semaine.date_debut)
    d.setDate(d.getDate() + i)
    return formatShort(d)
  }

  return (
    <div className="pdf-timetable-wrapper">
      <div className="timetable-header-info">
        <div>
          <h3>Emploi du temps - Semaine {semaine.numero}</h3>
          <p>{formatDate(semaine.date_debut)} au {formatDate(semaine.date_fin)} - {seances.length} seances - {displayGroups.length} groupes</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="session-badge badge-brouillon">Brouillon: {seances.filter(s => s.statut === 'brouillon').length}</span>
          <span className="session-badge badge-valide">Valide: {seances.filter(s => s.statut === 'valide').length}</span>
        </div>
      </div>

      <div className="pdf-table-scroll">
        <table className="pdf-table">
          <thead>
            <tr>
              <th className="th-groupe" rowSpan={2}>Groupe</th>
              {JOURS.map((jour, i) => (
                <th key={jour} className="th-day" colSpan={4}>
                  {jour}
                  <div className="th-day-date">{dayDate(i)}</div>
                </th>
              ))}
            </tr>
            <tr>
              {JOURS.map((_, ji) =>
                SEANCES.map(s => (
                  <th key={`${ji}_${s.num}`} className="th-seance">
                    <div>S{s.num}</div>
                    <div className="th-seance-time">{s.debut}</div>
                    <div className="th-seance-time">{s.fin}</div>
                  </th>
                ))
              )}
            </tr>
          </thead>
          <tbody>
            {displayGroups.map(g => (
              <tr key={g.id}>
                <td className="td-groupe">
                  <div className="groupe-code">{g.code}</div>
                  <div className="groupe-filiere">{g.filiere_code}</div>
                </td>
                {JOURS.map((_, ji) =>
                  SEANCES.map(s => {
                    const jour = ji + 1
                    const seance = lookup[g.code]?.[jour]?.[s.num]
                    return (
                      <td key={`${ji}_${s.num}`} className={`td-cell ${seance ? 'td-cell-filled' : 'td-cell-empty'}`}>
                        <CellContent seance={seance} onEdit={onEdit} onDelete={onDelete} />
                      </td>
                    )
                  })
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EditModal({ seance, salles, creneaux, onClose, onSave }) {
  const [creneauId, setCreneauId] = useState(seance.creneau_id)
  const [salleId, setSalleId] = useState(seance.salle_id || '')
  const [statut, setStatut] = useState(seance.statut)
  const [loading, setLoading] = useState(false)

  const handleSave = async () => {
    setLoading(true)
    try {
      await apiFetch(`${API}/seances/${seance.id}`, {
        method: 'PUT',
        body: JSON.stringify({ creneau_id: +creneauId, salle_id: salleId ? +salleId : null, statut })
      })
      onSave()
    } catch (e) { alert(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <h3>Modifier la seance</h3>
        <div style={{ background: '#f0f6ff', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13 }}>
          <strong>{seance.module_code}</strong> {seance.module_intitule}
        </div>
        <div className="modal-field">
          <label>Creneau</label>
          <select value={creneauId} onChange={e => setCreneauId(e.target.value)}>
            {creneaux.map(c => (
              <option key={c.id} value={c.id}>
                {JOURS[c.jour - 1]} S{c.numero_seance} ({c.heure_debut?.slice(0, 5)}-{c.heure_fin?.slice(0, 5)})
              </option>
            ))}
          </select>
        </div>
        <div className="modal-field">
          <label>Salle</label>
          <select value={salleId} onChange={e => setSalleId(e.target.value)}>
            <option value="">Distance</option>
            {salles.map(s => <option key={s.id} value={s.id}>{s.nom} ({s.type_code})</option>)}
          </select>
        </div>
        <div className="modal-field">
          <label>Statut</label>
          <select value={statut} onChange={e => setStatut(e.target.value)}>
            <option value="brouillon">Brouillon</option>
            <option value="valide">Valide</option>
          </select>
        </div>
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={loading}>
            {loading ? 'Enregistrement...' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Dashboard({ role, onLogout }) {
  const [activeNav, setActiveNav] = useState('emploi')
  const [semaines, setSemaines] = useState([])
  const [selectedSemaine, setSelectedSemaine] = useState(null)
  const [seances, setSeances] = useState([])
  const [stats, setStats] = useState(null)
  const [groupes, setGroupes] = useState([])
  const [professeurs, setProfesseurs] = useState([])
  const [salles, setSalles] = useState([])
  const [creneaux, setCreneaux] = useState([])
  const [filterFiliere, setFilterFiliere] = useState('all')
  const [loadingSeances, setLoadingSeances] = useState(false)
  const [loadingGen, setLoadingGen] = useState(false)
  const [editSeance, setEditSeance] = useState(null)
  const [toasts, setToasts] = useState([])
  const [dbStatus, setDbStatus] = useState(null)

  const addToast = useCallback((message, type) => {
    const id = Date.now()
    setToasts(t => [...t, { id, message, type: type || 'success' }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4500)
  }, [])

  const findCurrentWeek = useCallback((sw) => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return sw.find(s => today >= new Date(s.date_debut) && today <= new Date(s.date_fin)) || sw[0]
  }, [])

  useEffect(() => {
    const init = async () => {
      try {
        const [sw, g, p, sl, cr, hc] = await Promise.all([
          apiFetch(`${API}/semaines`),
          apiFetch(`${API}/groupes`),
          apiFetch(`${API}/professeurs`),
          apiFetch(`${API}/salles`),
          apiFetch(`${API}/creneaux`),
          apiFetch(`${API}/health`),
        ])
        setSemaines(sw); setGroupes(g); setProfesseurs(p); setSalles(sl); setCreneaux(cr)
        setDbStatus(hc.status)
        if (sw.length > 0) setSelectedSemaine(findCurrentWeek(sw))
      } catch (e) { setDbStatus('error'); addToast('Serveur inaccessible', 'error') }
    }
    init()
  }, [addToast, findCurrentWeek])

  useEffect(() => {
    if (!selectedSemaine) return
    const load = async () => {
      setLoadingSeances(true)
      try {
        const [sc, st] = await Promise.all([
          apiFetch(`${API}/emploi-du-temps/${selectedSemaine.id}`),
          apiFetch(`${API}/stats/${selectedSemaine.id}`),
        ])
        setSeances(sc); setStats(st)
      } catch (e) { addToast(e.message, 'error') }
      finally { setLoadingSeances(false) }
    }
    load()
  }, [selectedSemaine, addToast])

  const refreshSeances = useCallback(async () => {
    if (!selectedSemaine) return
    const [sc, st] = await Promise.all([
      apiFetch(`${API}/emploi-du-temps/${selectedSemaine.id}`),
      apiFetch(`${API}/stats/${selectedSemaine.id}`),
    ])
    setSeances(sc); setStats(st)
  }, [selectedSemaine])

  const handleGenerate = async () => {
    if (!selectedSemaine || !window.confirm(`Generer semaine ${selectedSemaine.numero} ?`)) return
    setLoadingGen(true)
    try {
      const res = await apiFetch(`${API}/generer/${selectedSemaine.id}`, { method: 'POST' })
      addToast(res.message, 'success'); await refreshSeances()
    } catch (e) { addToast(e.message, 'error') }
    finally { setLoadingGen(false) }
  }

  const handleValider = async () => {
    if (!selectedSemaine || !window.confirm('Valider?')) return
    await apiFetch(`${API}/semaines/${selectedSemaine.id}/valider`, { method: 'POST' })
    addToast('Valide', 'success'); await refreshSeances()
  }

  const handleVider = async () => {
    if (!selectedSemaine || !window.confirm(`Vider semaine ${selectedSemaine.numero} ?`)) return
    const res = await apiFetch(`${API}/vider-semaine/${selectedSemaine.id}`, { method: 'POST' })
    addToast(`${res.count} seances supprimees`, 'warning'); await refreshSeances()
  }

  const handleDelete = async (seance) => {
    if (!window.confirm(`Supprimer ${seance.module_code} ?`)) return
    await apiFetch(`${API}/seances/${seance.id}`, { method: 'DELETE' })
    addToast('Seance supprimee', 'warning'); await refreshSeances()
  }

  const handleEditSave = async () => {
    setEditSeance(null); addToast('Mise a jour', 'success'); await refreshSeances()
  }

  const semaineIdx = semaines.findIndex(s => s.id === selectedSemaine?.id)
  const prevSemaine = () => { if (semaineIdx < semaines.length - 1) setSelectedSemaine(semaines[semaineIdx + 1]) }
  const nextSemaine = () => { if (semaineIdx > 0) setSelectedSemaine(semaines[semaineIdx - 1]) }
  const goCurrentWeek = () => { if (semaines.length) setSelectedSemaine(findCurrentWeek(semaines)) }

  const filieresFromGroupes = [...new Set(groupes.map(g => g.filiere_code))].sort()

  return (
    <div className="dashboard">
      <ToastContainer toasts={toasts} />
      <aside className="dash-sidebar">
        <div className="dash-sidebar-logo">
          <div className="logo-icon">📅</div>
          <div><h2>GestEmploi</h2><span>ISTA NTIC 2</span></div>
        </div>
        <nav className="dash-nav">
          {[
            { id: 'emploi', icon: '📅', label: 'Emploi du temps' },
            { id: 'groupes', icon: '👥', label: 'Groupes' },
            { id: 'profs', icon: '👨‍🏫', label: 'Formateurs' },
            { id: 'salles', icon: '🏫', label: 'Salles' },
          ].map(item => (
            <button key={item.id} className={`dash-nav-item ${activeNav === item.id ? 'active' : ''}`} onClick={() => setActiveNav(item.id)}>
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        {activeNav === 'emploi' && (
          <div className="sidebar-week-info">
            <div className="sidebar-week-label">Semaine</div>
            {selectedSemaine && (
              <div>
                <div className="sidebar-week-num">S{selectedSemaine.numero}</div>
                <div className="sidebar-week-dates">{formatDate(selectedSemaine.date_debut)}<br />{formatDate(selectedSemaine.date_fin)}</div>
                <button className="btn-current-week" onClick={goCurrentWeek}>Semaine actuelle</button>
              </div>
            )}
          </div>
        )}
        <div className="dash-sidebar-footer">
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginBottom: 8, paddingLeft: 14 }}>
            DB: <span style={{ color: dbStatus === 'ok' ? '#4ade80' : '#f87171' }}>{dbStatus === 'ok' ? 'Connectee' : 'Erreur'}</span>
          </div>
          <button className="dash-logout-btn" onClick={onLogout}><span>🚪</span><span>Deconnexion</span></button>
        </div>
      </aside>

      <main className="dash-main">
        <header className="dash-topbar">
          <h1>
            {activeNav === 'emploi' && '📅 Emploi du temps'}
            {activeNav === 'groupes' && '👥 Groupes'}
            {activeNav === 'profs' && '👨‍🏫 Formateurs'}
            {activeNav === 'salles' && '🏫 Salles'}
          </h1>
          <div className="topbar-right">
            <span style={{ fontSize: 12, color: '#64748b' }}>👤 {role === 'admin' ? 'Administrateur' : 'Formateur'}</span>
          </div>
        </header>

        <div className="dash-content">
          {activeNav === 'emploi' && (
            <>
              <div className="stats-grid">
                <div className="stat-card"><div className="stat-icon blue">📋</div><div className="stat-info"><h3>{stats?.total ?? '-'}</h3><p>Seances</p></div></div>
                <div className="stat-card"><div className="stat-icon amber">✏️</div><div className="stat-info"><h3>{stats?.brouillon ?? '-'}</h3><p>Brouillon</p></div></div>
                <div className="stat-card"><div className="stat-icon green">✅</div><div className="stat-info"><h3>{stats?.valide ?? '-'}</h3><p>Validees</p></div></div>
                <div className="stat-card"><div className="stat-icon violet">👥</div><div className="stat-info"><h3>{stats?.groupes_actifs ?? '-'}</h3><p>Groupes</p></div></div>
              </div>

              <div className="controls-bar">
                <div className="week-nav">
                  <button className="btn btn-ghost" onClick={prevSemaine} disabled={semaineIdx >= semaines.length - 1}>◀</button>
                  <select style={{ minWidth: 240 }} value={selectedSemaine?.id || ''} onChange={e => setSelectedSemaine(semaines.find(s => s.id === +e.target.value))}>
                    {semaines.map(s => (
                      <option key={s.id} value={s.id}>Semaine {s.numero} — {formatShort(s.date_debut)} au {formatShort(s.date_fin)}</option>
                    ))}
                  </select>
                  <button className="btn btn-ghost" onClick={nextSemaine} disabled={semaineIdx <= 0}>▶</button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, color: '#475569' }}>Filiere:</label>
                  <select value={filterFiliere} onChange={e => setFilterFiliere(e.target.value)} style={{ minWidth: 200 }}>
                    <option value="all">Toutes les filieres</option>
                    {filieresFromGroupes.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                </div>

                <div style={{ flex: 1 }} />

                {role === 'admin' && (
                  <>
                    <button className="btn btn-primary" onClick={handleGenerate} disabled={loadingGen || !selectedSemaine}>
                      {loadingGen ? 'Generation...' : `⚡ Generer S.${selectedSemaine?.numero || ''}`}
                    </button>
                    <button className="btn btn-success" onClick={handleValider} disabled={!selectedSemaine || !seances.length}>✔ Valider tout</button>
                    <button className="btn btn-danger" onClick={handleVider} disabled={!selectedSemaine || !seances.length}>🗑 Vider</button>
                  </>
                )}
              </div>

              {loadingSeances ? (
                <div className="loading-state"><span className="spinner" /> Chargement...</div>
              ) : (
                <TimetableGrid seances={seances} semaine={selectedSemaine} groupes={groupes} filterFiliere={filterFiliere} onEdit={role === 'admin' ? setEditSeance : null} onDelete={role === 'admin' ? handleDelete : null} />
              )}
            </>
          )}

          {activeNav === 'groupes' && (
            <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e5e9f0', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr style={{ background: '#1a5fa8', color: '#fff' }}>
                  {['Code', 'Filiere', 'Annee', 'Effectif', 'Mode', 'Regime'].map(h => <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: 13 }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {groupes.map((g, i) => (
                    <tr key={g.id} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc', borderBottom: '1px solid #e5e9f0' }}>
                      <td style={{ padding: '10px 16px', fontWeight: 700, color: '#1a5fa8' }}>{g.code}</td>
                      <td style={{ padding: '10px 16px', fontSize: 12 }}>{g.filiere_nom}</td>
                      <td style={{ padding: '10px 16px' }}>{g.annee_etude}</td>
                      <td style={{ padding: '10px 16px' }}>{g.effectif}</td>
                      <td style={{ padding: '10px 16px', fontSize: 12 }}>{g.mode_formation}</td>
                      <td style={{ padding: '10px 16px', fontSize: 12 }}>{g.regime}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeNav === 'profs' && (
            <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e5e9f0', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr style={{ background: '#1a5fa8', color: '#fff' }}>
                  {['Matricule', 'Nom', 'Statut', 'Email', 'H max'].map(h => <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: 13 }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {professeurs.map((p, i) => (
                    <tr key={p.id} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc', borderBottom: '1px solid #e5e9f0' }}>
                      <td style={{ padding: '10px 16px', fontWeight: 700, color: '#1a5fa8', fontSize: 12 }}>{p.matricule}</td>
                      <td style={{ padding: '10px 16px', fontWeight: 600 }}>{p.nom_complet}</td>
                      <td style={{ padding: '10px 16px' }}>{p.statut}</td>
                      <td style={{ padding: '10px 16px', fontSize: 12, color: '#64748b' }}>{p.email || '-'}</td>
                      <td style={{ padding: '10px 16px' }}>{p.heures_max_semaine || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeNav === 'salles' && (
            <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e5e9f0', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr style={{ background: '#1a5fa8', color: '#fff' }}>
                  {['Salle', 'Type', 'Capacite', 'Statut'].map(h => <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: 13 }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {salles.map((s, i) => (
                    <tr key={s.id} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc', borderBottom: '1px solid #e5e9f0' }}>
                      <td style={{ padding: '10px 16px', fontWeight: 700, color: '#1a5fa8' }}>{s.nom}</td>
                      <td style={{ padding: '10px 16px', fontSize: 12 }}>{s.type_libelle}</td>
                      <td style={{ padding: '10px 16px' }}>{s.capacite || '-'}</td>
                      <td style={{ padding: '10px 16px', fontSize: 12 }}>{s.actif ? 'Active' : 'Inactive'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {editSeance && (
        <EditModal seance={editSeance} salles={salles} creneaux={creneaux} onClose={() => setEditSeance(null)} onSave={handleEditSave} />
      )}
    </div>
  )
}
