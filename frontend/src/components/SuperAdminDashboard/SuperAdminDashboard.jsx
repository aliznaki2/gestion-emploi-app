import React, { useState, useEffect, useCallback } from 'react'
import './SuperAdminDashboard.css'

const API = 'http://localhost:3001/api/superadmin'

const apiFetch = async (url, opts = {}) => {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!r.ok) {
    let errMsg = 'Erreur serveur'
    try {
      const e = await r.json()
      errMsg = e.error || e.detail || errMsg
    } catch {}
    throw new Error(errMsg)
  }
  return r.json()
}

const EMPTY_ETAB = {
  code: '', nom: '', nom_court: '', ville: '', quartier: '',
  adresse: '', email: '', telephone: '', site_web: '',
  couleur_accent: '#1a5fa8', max_formateurs: 100, max_groupes: 50,
}

const EMPTY_ADMIN = { username: '', password: '', email: '', first_name: '', last_name: '' }

export default function SuperAdminDashboard({ onLogout }) {
  const [activeNav, setActiveNav] = useState('etablissements') // 'etablissements' | 'demandes' | 'stats'
  const [etablissements, setEtablissements] = useState([])
  const [demandes, setDemandes] = useState([])
  const [demandesCounts, setDemandesCounts] = useState({ total: 0, en_attente: 0, approuvee: 0, refusee: 0 })
  const [demandeFilter, setDemandeFilter] = useState('tous') // 'tous' | 'en_attente' | 'approuvee' | 'refusee'
  const [statsGlobales, setStatsGlobales] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toasts, setToasts] = useState([])

  // Modal Etablissement (Create / Edit)
  const [showModal, setShowModal] = useState(false)
  const [modalMode, setModalMode] = useState('create') // 'create' | 'edit'
  const [formData, setFormData] = useState({ ...EMPTY_ETAB })
  const [editingId, setEditingId] = useState(null)

  // Modal Admins
  const [showAdminModal, setShowAdminModal] = useState(false)
  const [adminEtab, setAdminEtab] = useState(null)
  const [admins, setAdmins] = useState([])
  const [newAdmin, setNewAdmin] = useState({ ...EMPTY_ADMIN })

  // Admin Edit (Email, Nom, Prénom, Username)
  const [editingAdmin, setEditingAdmin] = useState(null)

  // Admin Password Reset Modal
  const [passwordModalAdmin, setPasswordModalAdmin] = useState(null)
  const [newAdminPassword, setNewAdminPassword] = useState('')

  // Delete Etablissement Confirm
  const [deletingEtab, setDeletingEtab] = useState(null)

  // Detail / Stats Modal
  const [detailEtab, setDetailEtab] = useState(null)

  // Modal Détail Demande d'abonnement
  const [detailDemande, setDetailDemande] = useState(null)

  // Modal Approbation Demande d'abonnement
  const [approvingDemande, setApprovingDemande] = useState(null)
  const [approvalData, setApprovalData] = useState({
    code: '',
    creer_etablissement: true,
    admin_username: '',
    admin_password: '',
    notes_admin: '',
  })

  // Confirmation Refus Demande
  const [rejectingDemande, setRejectingDemande] = useState(null)
  const [rejectReason, setRejectReason] = useState('')

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts(t => [...t, { id, message, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000)
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [etabs, stats, demData] = await Promise.all([
        apiFetch(`${API}/etablissements`),
        apiFetch(`${API}/stats-globales`),
        apiFetch(`${API}/demandes`).catch(() => ({ demandes: [], counts: { total: 0, en_attente: 0, approuvee: 0, refusee: 0 } })),
      ])
      setEtablissements(etabs)
      setStatsGlobales(stats)
      setDemandes(demData.demandes || [])
      setDemandesCounts(demData.counts || { total: 0, en_attente: 0, approuvee: 0, refusee: 0 })
    } catch (e) {
      addToast('Impossible de joindre le serveur backend.', 'error')
    }
    setLoading(false)
  }, [addToast])

  useEffect(() => { loadData() }, [loadData])

  // ─── CRUD Établissements ─────────────────────────────────────────────
  const openCreate = () => {
    setFormData({ ...EMPTY_ETAB })
    setModalMode('create')
    setEditingId(null)
    setShowModal(true)
  }

  const openEdit = (etab) => {
    setFormData({
      code: etab.code, nom: etab.nom, nom_court: etab.nom_court,
      ville: etab.ville, quartier: etab.quartier, adresse: etab.adresse,
      email: etab.email, telephone: etab.telephone, site_web: etab.site_web,
      couleur_accent: etab.couleur_accent,
      max_formateurs: etab.max_formateurs, max_groupes: etab.max_groupes,
    })
    setModalMode('edit')
    setEditingId(etab.id)
    setShowModal(true)
  }

  const handleSave = async () => {
    try {
      if (modalMode === 'create') {
        await apiFetch(`${API}/etablissements`, {
          method: 'POST', body: JSON.stringify(formData),
        })
        addToast('Établissement créé avec succès.')
      } else {
        await apiFetch(`${API}/etablissements/${editingId}`, {
          method: 'PUT', body: JSON.stringify(formData),
        })
        addToast('Établissement mis à jour avec succès.')
      }
      setShowModal(false)
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  const handleAction = async (etab, action) => {
    try {
      await apiFetch(`${API}/etablissements/${etab.id}/${action}`, { method: 'POST' })
      const labels = { activer: 'activé', desactiver: 'désactivé', suspendre: 'suspendu' }
      addToast(`Établissement ${etab.nom_court || etab.code} ${labels[action]}.`)
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  const confirmDelete = async () => {
    if (!deletingEtab) return
    try {
      await apiFetch(`${API}/etablissements/${deletingEtab.id}`, { method: 'DELETE' })
      addToast(`Établissement ${deletingEtab.nom_court || deletingEtab.code} supprimé.`)
      setDeletingEtab(null)
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  // ─── Gestion des Administrateurs ─────────────────────────────────────
  const openAdmins = async (etab) => {
    setAdminEtab(etab)
    setNewAdmin({ ...EMPTY_ADMIN })
    setEditingAdmin(null)
    setPasswordModalAdmin(null)
    try {
      const list = await apiFetch(`${API}/etablissements/${etab.id}/admins`)
      setAdmins(list)
    } catch { setAdmins([]) }
    setShowAdminModal(true)
  }

  const addAdmin = async () => {
    if (!newAdmin.username || !newAdmin.password) {
      addToast('Le nom d\'utilisateur et le mot de passe sont obligatoires.', 'error')
      return
    }
    try {
      await apiFetch(`${API}/etablissements/${adminEtab.id}/admins`, {
        method: 'POST', body: JSON.stringify(newAdmin),
      })
      addToast('Administrateur ajouté avec succès.')
      setNewAdmin({ ...EMPTY_ADMIN })
      const list = await apiFetch(`${API}/etablissements/${adminEtab.id}/admins`)
      setAdmins(list)
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  const saveEditedAdmin = async () => {
    if (!editingAdmin) return
    try {
      await apiFetch(`${API}/etablissements/${adminEtab.id}/admins/${editingAdmin.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          username: editingAdmin.username,
          email: editingAdmin.email,
          first_name: editingAdmin.first_name,
          last_name: editingAdmin.last_name,
        }),
      })
      addToast('Informations de l\'administrateur mises à jour.')
      setEditingAdmin(null)
      const list = await apiFetch(`${API}/etablissements/${adminEtab.id}/admins`)
      setAdmins(list)
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  const saveNewAdminPassword = async () => {
    if (!passwordModalAdmin || !newAdminPassword.trim()) {
      addToast('Veuillez saisir un mot de passe valide.', 'error')
      return
    }
    try {
      await apiFetch(`${API}/etablissements/${adminEtab.id}/admins/${passwordModalAdmin.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ password: newAdminPassword.trim() }),
      })
      addToast(`Mot de passe modifié pour ${passwordModalAdmin.username}.`)
      setPasswordModalAdmin(null)
      setNewAdminPassword('')
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  const removeAdmin = async (userId) => {
    try {
      await apiFetch(`${API}/etablissements/${adminEtab.id}/admins/${userId}`, { method: 'DELETE' })
      addToast('Administrateur retiré.')
      const list = await apiFetch(`${API}/etablissements/${adminEtab.id}/admins`)
      setAdmins(list)
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  // ─── Actions sur les Demandes d'Abonnement ────────────────────────────
  const openApproveModal = (demande) => {
    const defaultCode = (demande.nom_etablissement || 'ISTA')
      .replace(/[^a-zA-Z0-9]/g, '')
      .slice(0, 6)
      .toUpperCase()
    setApprovalData({
      code: defaultCode,
      creer_etablissement: true,
      admin_username: `admin_${defaultCode.toLowerCase()}`,
      admin_password: 'Admin2026*',
      notes_admin: '',
    })
    setApprovingDemande(demande)
  }

  const confirmApproveDemande = async () => {
    if (!approvingDemande) return
    try {
      await apiFetch(`${API}/demandes/${approvingDemande.id}/approuver`, {
        method: 'POST',
        body: JSON.stringify(approvalData),
      })
      addToast(`Demande de ${approvingDemande.nom_etablissement} approuvée avec succès !`)
      setApprovingDemande(null)
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  const confirmRejectDemande = async () => {
    if (!rejectingDemande) return
    try {
      await apiFetch(`${API}/demandes/${rejectingDemande.id}/refuser`, {
        method: 'POST',
        body: JSON.stringify({ notes_admin: rejectReason }),
      })
      addToast(`Demande de ${rejectingDemande.nom_etablissement} refusée.`)
      setRejectingDemande(null)
      setRejectReason('')
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  const deleteDemande = async (demandeId) => {
    try {
      await apiFetch(`${API}/demandes/${demandeId}`, { method: 'DELETE' })
      addToast('Demande supprimée.')
      loadData()
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  // ─── Stats Détail ───────────────────────────────────────────────────
  const openDetail = async (etab) => {
    try {
      const data = await apiFetch(`${API}/etablissements/${etab.id}/stats`)
      setDetailEtab(data)
    } catch (e) {
      addToast(e.message, 'error')
    }
  }

  // ─── Statut Badge ───────────────────────────────────────────────────
  const renderStatusBadge = (etab) => {
    if (etab.suspendu) {
      return (
        <span className="sa-badge sa-badge--suspended">
          <span className="sa-badge-dot"></span>
          Suspendu
        </span>
      )
    }
    if (!etab.actif) {
      return (
        <span className="sa-badge sa-badge--inactive">
          <span className="sa-badge-dot"></span>
          Inactif
        </span>
      )
    }
    return (
      <span className="sa-badge sa-badge--active">
        <span className="sa-badge-dot"></span>
        Actif
      </span>
    )
  }

  const renderDemandeBadge = (demande) => {
    if (demande.statut === 'approuvee') {
      return (
        <span className="sa-badge sa-badge--active">
          <span className="sa-badge-dot"></span>
          Approuvée
        </span>
      )
    }
    if (demande.statut === 'refusee') {
      return (
        <span className="sa-badge sa-badge--inactive">
          <span className="sa-badge-dot"></span>
          Refusée
        </span>
      )
    }
    return (
      <span className="sa-badge sa-badge--suspended">
        <span className="sa-badge-dot"></span>
        En attente
      </span>
    )
  }

  const filteredDemandes = demandes.filter(d => {
    if (demandeFilter === 'tous') return true
    return d.statut === demandeFilter
  })

  return (
    <div className="sa-layout">
      {/* Notifications Toast */}
      <div className="sa-toasts" aria-live="polite">
        {toasts.map(t => (
          <div key={t.id} className={`sa-toast sa-toast--${t.type}`}>
            {t.type === 'success' ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            )}
            <span>{t.message}</span>
          </div>
        ))}
      </div>

      {/* ─── Barre Latérale (Sidebar) ─── */}
      <aside className="sa-sidebar">
        <div className="sa-sidebar-logo">
          <div className="sa-sidebar-brand-mark">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <div className="sa-sidebar-brand-text">
            <h2>GestEmploi</h2>
            <span>Portail Super Admin</span>
          </div>
        </div>

        <nav className="sa-nav">
          <span className="sa-nav-section">Administration SaaS</span>

          <button
            className={`sa-nav-item ${activeNav === 'etablissements' ? 'active' : ''}`}
            onClick={() => setActiveNav('etablissements')}
          >
            <span className="sa-nav-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="4" y="2" width="16" height="20" rx="2" ry="2"/>
                <line x1="9" y1="22" x2="9" y2="22.01"/>
                <line x1="15" y1="22" x2="15" y2="22.01"/>
                <line x1="8" y1="6" x2="8.01" y2="6"/>
                <line x1="16" y1="6" x2="16.01" y2="6"/>
                <line x1="8" y1="10" x2="8.01" y2="10"/>
                <line x1="16" y1="10" x2="16.01" y2="10"/>
                <line x1="8" y1="14" x2="8.01" y2="14"/>
                <line x1="16" y1="14" x2="16.01" y2="14"/>
                <line x1="8" y1="18" x2="8.01" y2="18"/>
                <line x1="16" y1="18" x2="16.01" y2="18"/>
              </svg>
            </span>
            <span>Établissements</span>
          </button>

          <button
            className={`sa-nav-item ${activeNav === 'demandes' ? 'active' : ''}`}
            onClick={() => setActiveNav('demandes')}
          >
            <span className="sa-nav-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </span>
            <span>Demandes d'adhésion</span>
            {demandesCounts.en_attente > 0 && (
              <span className="sa-nav-badge" title={`${demandesCounts.en_attente} en attente`}>
                {demandesCounts.en_attente}
              </span>
            )}
          </button>

          <button
            className={`sa-nav-item ${activeNav === 'stats' ? 'active' : ''}`}
            onClick={() => setActiveNav('stats')}
          >
            <span className="sa-nav-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </span>
            <span>Statistiques Globales</span>
          </button>
        </nav>

        <div className="sa-sidebar-footer">
          <button className="sa-logout-btn" onClick={onLogout}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Déconnexion</span>
          </button>
        </div>
      </aside>

      {/* ─── Contenu Principal (Main Area) ─── */}
      <main className="sa-main">
        <header className="sa-topbar">
          <div className="sa-topbar-heading">
            <h1>
              {activeNav === 'etablissements' && 'Gestion des Établissements'}
              {activeNav === 'demandes' && 'Demandes d\'adhésion au réseau'}
              {activeNav === 'stats' && 'Statistiques Globales du Réseau'}
            </h1>
            <p className="sa-topbar-sub">Console de supervision et gestion multi-tenant</p>
          </div>
          <div className="sa-topbar-user">
            <div className="sa-topbar-avatar">SA</div>
            <span className="sa-topbar-username">Super Administrateur</span>
            <span className="sa-topbar-role">Super Admin</span>
          </div>
        </header>

        <div className="sa-content">
          {loading ? (
            <div className="sa-loading">Chargement des données...</div>
          ) : activeNav === 'etablissements' ? (
            <>
              <div className="sa-toolbar">
                <div className="sa-toolbar-info">
                  <strong>{etablissements.length}</strong> établissement{etablissements.length > 1 ? 's' : ''} configuré{etablissements.length > 1 ? 's' : ''}
                </div>
                <button className="sa-btn sa-btn--primary" onClick={openCreate}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  <span>Nouvel Établissement</span>
                </button>
              </div>

              <div className="sa-table-wrap">
                <table className="sa-table">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Établissement</th>
                      <th>Ville</th>
                      <th>Statut</th>
                      <th>Formateurs</th>
                      <th>Groupes</th>
                      <th>Salles</th>
                      <th>Admins</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {etablissements.map(etab => (
                      <tr key={etab.id}>
                        <td><strong>{etab.code}</strong></td>
                        <td>
                          <div>
                            <span style={{ fontWeight: 600 }}>{etab.nom_court || etab.nom}</span>
                            {etab.nom_court && etab.nom !== etab.nom_court && (
                              <div style={{ fontSize: '11px', color: '#64748b' }}>{etab.nom}</div>
                            )}
                          </div>
                        </td>
                        <td>{etab.ville || '—'}</td>
                        <td>{renderStatusBadge(etab)}</td>
                        <td>{etab.stats?.nb_formateurs ?? '0'}</td>
                        <td>{etab.stats?.nb_groupes ?? '0'}</td>
                        <td>{etab.stats?.nb_salles ?? '0'}</td>
                        <td>{etab.stats?.nb_admins ?? '0'}</td>
                        <td>
                          <div className="sa-actions" style={{ justifyContent: 'flex-end' }}>
                            <button
                              className="sa-btn-icon sa-btn-icon--primary"
                              title="Consulter les statistiques"
                              onClick={() => openDetail(etab)}
                            >
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                            </button>

                            <button
                              className="sa-btn-icon"
                              title="Gérer les administrateurs (email, mot de passe)"
                              onClick={() => openAdmins(etab)}
                            >
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                            </button>

                            <button
                              className="sa-btn-icon"
                              title="Modifier l'établissement"
                              onClick={() => openEdit(etab)}
                            >
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>

                            {etab.actif && !etab.suspendu && (
                              <>
                                <button
                                  className="sa-btn-icon sa-btn-icon--warn"
                                  title="Suspendre l'établissement"
                                  onClick={() => handleAction(etab, 'suspendre')}
                                >
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                                </button>
                                <button
                                  className="sa-btn-icon sa-btn-icon--warn"
                                  title="Désactiver l'établissement"
                                  onClick={() => handleAction(etab, 'desactiver')}
                                >
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                                </button>
                              </>
                            )}

                            {(!etab.actif || etab.suspendu) && (
                              <button
                                className="sa-btn-icon sa-btn-icon--success"
                                title="Activer l'établissement"
                                onClick={() => handleAction(etab, 'activer')}
                              >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                              </button>
                            )}

                            <button
                              className="sa-btn-icon sa-btn-icon--danger"
                              title="Supprimer l'établissement"
                              onClick={() => setDeletingEtab(etab)}
                            >
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {etablissements.length === 0 && (
                      <tr>
                        <td colSpan="9" className="sa-empty">Aucun établissement enregistré.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : activeNav === 'demandes' ? (
            /* ─── Demandes d'Abonnement ─── */
            <>
              <div className="sa-tabs">
                <button
                  className={`sa-tab-btn ${demandeFilter === 'tous' ? 'active' : ''}`}
                  onClick={() => setDemandeFilter('tous')}
                >
                  Toutes <span className="sa-tab-count">{demandesCounts.total}</span>
                </button>
                <button
                  className={`sa-tab-btn ${demandeFilter === 'en_attente' ? 'active' : ''}`}
                  onClick={() => setDemandeFilter('en_attente')}
                >
                  En attente <span className="sa-tab-count" style={{ background: demandesCounts.en_attente > 0 ? '#fef3c7' : undefined, color: demandesCounts.en_attente > 0 ? '#b45309' : undefined }}>{demandesCounts.en_attente}</span>
                </button>
                <button
                  className={`sa-tab-btn ${demandeFilter === 'approuvee' ? 'active' : ''}`}
                  onClick={() => setDemandeFilter('approuvee')}
                >
                  Approuvées <span className="sa-tab-count">{demandesCounts.approuvee}</span>
                </button>
                <button
                  className={`sa-tab-btn ${demandeFilter === 'refusee' ? 'active' : ''}`}
                  onClick={() => setDemandeFilter('refusee')}
                >
                  Refusées <span className="sa-tab-count">{demandesCounts.refusee}</span>
                </button>
              </div>

              <div className="sa-table-wrap">
                <table className="sa-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Établissement</th>
                      <th>Ville</th>
                      <th>Contact / Rôle</th>
                      <th>Email & Téléphone</th>
                      <th>Statut</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDemandes.map(d => (
                      <tr key={d.id}>
                        <td style={{ fontSize: '12px', color: '#64748b' }}>
                          {d.date_demande ? new Date(d.date_demande).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                        </td>
                        <td>
                          <div>
                            <strong style={{ color: '#0f172a' }}>{d.nom_etablissement}</strong>
                            {d.etablissement_cree_nom && (
                              <div style={{ fontSize: '11px', color: '#16a34a' }}>
                                Établissement lié : {d.etablissement_cree_nom}
                              </div>
                            )}
                          </div>
                        </td>
                        <td>{d.ville || '—'}</td>
                        <td>
                          <div>
                            <span style={{ fontWeight: 600 }}>{d.nom_contact || '—'}</span>
                            {d.role_contact && <div style={{ fontSize: '11px', color: '#64748b' }}>{d.role_contact}</div>}
                          </div>
                        </td>
                        <td>
                          <div style={{ fontSize: '12.5px' }}>
                            <div>{d.email}</div>
                            {d.telephone && <div style={{ fontSize: '11.5px', color: '#64748b' }}>{d.telephone}</div>}
                          </div>
                        </td>
                        <td>{renderDemandeBadge(d)}</td>
                        <td>
                          <div className="sa-actions" style={{ justifyContent: 'flex-end', gap: '6px' }}>
                            <button
                              className="sa-btn"
                              style={{ padding: '4px 10px', fontSize: '12px' }}
                              title="Consulter les détails et le message"
                              onClick={() => setDetailDemande(d)}
                            >
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                              <span>Détails</span>
                            </button>

                            {d.statut === 'en_attente' && (
                              <>
                                <button
                                  className="sa-btn"
                                  style={{ padding: '4px 11px', fontSize: '12px', background: '#16a34a', borderColor: '#16a34a', color: '#fff' }}
                                  title="Approuver et créer l'établissement"
                                  onClick={() => openApproveModal(d)}
                                >
                                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                                  <span>Approuver</span>
                                </button>
                                <button
                                  className="sa-btn"
                                  style={{ padding: '4px 10px', fontSize: '12px', background: '#fef2f2', borderColor: '#fca5a5', color: '#dc2626' }}
                                  title="Refuser la demande"
                                  onClick={() => setRejectingDemande(d)}
                                >
                                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                                  <span>Refuser</span>
                                </button>
                              </>
                            )}

                            <button
                              className="sa-btn-icon sa-btn-icon--danger"
                              style={{ padding: '4px 7px' }}
                              title="Supprimer la demande"
                              onClick={() => deleteDemande(d.id)}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredDemandes.length === 0 && (
                      <tr>
                        <td colSpan="7" className="sa-empty">Aucune demande d'abonnement dans cette catégorie.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            /* ─── Statistiques Globales ─── */
            statsGlobales && (
              <div className="sa-stats-grid">
                <div className="sa-stat-card">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="9" y1="22" x2="9" y2="22.01"/><line x1="15" y1="22" x2="15" y2="22.01"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{statsGlobales.nb_etablissements}</div>
                    <div className="sa-stat-label">Total Établissements</div>
                  </div>
                </div>

                <div className="sa-stat-card sa-stat-card--green">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{statsGlobales.nb_etablissements_actifs}</div>
                    <div className="sa-stat-label">Établissements Actifs</div>
                  </div>
                </div>

                <div className="sa-stat-card sa-stat-card--amber">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{statsGlobales.nb_etablissements_suspendus}</div>
                    <div className="sa-stat-label">Suspendus</div>
                  </div>
                </div>

                <div className="sa-stat-card sa-stat-card--red">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{statsGlobales.nb_etablissements_inactifs}</div>
                    <div className="sa-stat-label">Inactifs</div>
                  </div>
                </div>

                <div className="sa-stat-card">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{demandesCounts.total}</div>
                    <div className="sa-stat-label">Demandes d'adhésion ({demandesCounts.en_attente} en attente)</div>
                  </div>
                </div>

                <div className="sa-stat-card">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{statsGlobales.nb_formateurs_total}</div>
                    <div className="sa-stat-label">Formateurs Enregistrés</div>
                  </div>
                </div>

                <div className="sa-stat-card">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{statsGlobales.nb_groupes_total}</div>
                    <div className="sa-stat-label">Groupes de Stagiaires</div>
                  </div>
                </div>

                <div className="sa-stat-card">
                  <div className="sa-stat-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
                  </div>
                  <div>
                    <div className="sa-stat-value">{statsGlobales.nb_salles_total}</div>
                    <div className="sa-stat-label">Salles et Locaux</div>
                  </div>
                </div>
              </div>
            )
          )}
        </div>
      </main>

      {/* ─── Modal Détail Demande d'Abonnement ─── */}
      {detailDemande && (
        <div className="sa-modal-overlay" onClick={() => setDetailDemande(null)}>
          <div className="sa-modal" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>Demande d'Adhésion — {detailDemande.nom_etablissement}</h2>
              <button className="sa-modal-close" onClick={() => setDetailDemande(null)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '15px', color: '#0f172a' }}>{detailDemande.nom_etablissement}</h3>
                  <span style={{ fontSize: '12px', color: '#64748b' }}>Ville : {detailDemande.ville || 'Non précisée'}</span>
                </div>
                <div>{renderDemandeBadge(detailDemande)}</div>
              </div>

              <div className="sa-form-grid" style={{ marginBottom: 16 }}>
                <div>
                  <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>RESPONSABLE DU CONTACT</span>
                  <div style={{ fontSize: '13.5px', fontWeight: 600, color: '#0f172a' }}>{detailDemande.nom_contact || '—'}</div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>{detailDemande.role_contact || '—'}</div>
                </div>
                <div>
                  <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>COORDONNÉES</span>
                  <div style={{ fontSize: '13.5px', color: '#0f172a' }}>{detailDemande.email}</div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>{detailDemande.telephone || 'Non renseigné'}</div>
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>MESSAGE / BESOINS EXPRIMÉS</span>
                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginTop: 4, fontSize: '13px', color: '#334155', minHeight: 60, whiteSpace: 'pre-wrap' }}>
                  {detailDemande.message || 'Aucun message spécifique laissé par le demandeur.'}
                </div>
              </div>

              {detailDemande.notes_admin && (
                <div style={{ marginBottom: 16 }}>
                  <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>NOTES DU SUPER ADMINISTRATEUR</span>
                  <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: 10, marginTop: 4, fontSize: '12.5px', color: '#92400e' }}>
                    {detailDemande.notes_admin}
                  </div>
                </div>
              )}
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setDetailDemande(null)}>Fermer</button>
              {detailDemande.statut === 'en_attente' && (
                <>
                  <button
                    className="sa-btn sa-btn--danger"
                    onClick={() => {
                      const d = detailDemande
                      setDetailDemande(null)
                      setRejectingDemande(d)
                    }}
                  >
                    Refuser la Demande
                  </button>
                  <button
                    className="sa-btn sa-btn--primary"
                    style={{ background: '#16a34a', borderColor: '#16a34a' }}
                    onClick={() => {
                      const d = detailDemande
                      setDetailDemande(null)
                      openApproveModal(d)
                    }}
                  >
                    Approuver la Demande...
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal Validation / Approbation Demande d'Abonnement ─── */}
      {approvingDemande && (
        <div className="sa-modal-overlay" onClick={() => setApprovingDemande(null)}>
          <div className="sa-modal" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>Approuver la Demande & Créer l'Établissement</h2>
              <button className="sa-modal-close" onClick={() => setApprovingDemande(null)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <p style={{ margin: '0 0 16px', fontSize: '13.5px', color: '#334155', lineHeight: 1.5 }}>
                En approuvant cette demande pour <strong>{approvingDemande.nom_etablissement}</strong> ({approvingDemande.ville}), un espace de travail dédié sera automatiquement initialisé dans la plateforme.
              </p>

              <div className="sa-form-grid">
                <label>
                  <span>Code Établissement *</span>
                  <input
                    value={approvalData.code}
                    onChange={e => setApprovalData({ ...approvalData, code: e.target.value.toUpperCase() })}
                    placeholder="ex: ISIC, NTIC3"
                    required
                  />
                </label>
                <label>
                  <span>Compte Administrateur Initial (Login)</span>
                  <input
                    value={approvalData.admin_username}
                    onChange={e => setApprovalData({ ...approvalData, admin_username: e.target.value })}
                  />
                </label>
                <label>
                  <span>Mot de Passe Administrateur</span>
                  <input
                    type="text"
                    value={approvalData.admin_password}
                    onChange={e => setApprovalData({ ...approvalData, admin_password: e.target.value })}
                  />
                </label>
                <label className="sa-form-full">
                  <span>Notes Internes</span>
                  <textarea
                    rows="2"
                    value={approvalData.notes_admin}
                    onChange={e => setApprovalData({ ...approvalData, notes_admin: e.target.value })}
                    placeholder="Commentaire de validation..."
                  />
                </label>
              </div>
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setApprovingDemande(null)}>Annuler</button>
              <button className="sa-btn sa-btn--primary" onClick={confirmApproveDemande}>
                Valider & Déployer l'Établissement
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal Refus Demande ─── */}
      {rejectingDemande && (
        <div className="sa-modal-overlay" onClick={() => setRejectingDemande(null)}>
          <div className="sa-modal sa-modal--sm" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>Refuser la Demande d'Adhésion</h2>
              <button className="sa-modal-close" onClick={() => setRejectingDemande(null)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <p style={{ margin: '0 0 14px', fontSize: '13.5px', color: '#334155' }}>
                Refuser la demande déposée par <strong>{rejectingDemande.nom_etablissement}</strong> ?
              </p>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: '#334155' }}>Motif du refus (optionnel)</span>
                <textarea
                  rows="3"
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  placeholder="Raison du refus pour archivage..."
                  style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '13px' }}
                />
              </label>
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setRejectingDemande(null)}>Annuler</button>
              <button className="sa-btn sa-btn--danger" onClick={confirmRejectDemande}>
                Confirmer le Refus
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal Créer / Modifier Établissement ─── */}
      {showModal && (
        <div className="sa-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="sa-modal" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>{modalMode === 'create' ? 'Nouvel Établissement' : 'Modifier les Informations de l\'Établissement'}</h2>
              <button className="sa-modal-close" onClick={() => setShowModal(false)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <div className="sa-form-grid">
                <label>
                  <span>Code Établissement *</span>
                  <input
                    value={formData.code}
                    onChange={e => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    placeholder="ex: NTIC2, ISIC, CFPM"
                    required
                  />
                </label>
                <label>
                  <span>Nom Court</span>
                  <input
                    value={formData.nom_court}
                    onChange={e => setFormData({ ...formData, nom_court: e.target.value })}
                    placeholder="ex: ISTA NTIC 2"
                  />
                </label>
                <label className="sa-form-full">
                  <span>Nom Complet *</span>
                  <input
                    value={formData.nom}
                    onChange={e => setFormData({ ...formData, nom: e.target.value })}
                    placeholder="ex: Institut Spécialisé de Technologie Appliquée..."
                    required
                  />
                </label>
                <label>
                  <span>Ville</span>
                  <input
                    value={formData.ville}
                    onChange={e => setFormData({ ...formData, ville: e.target.value })}
                    placeholder="ex: Casablanca, Rabat"
                  />
                </label>
                <label>
                  <span>Quartier / District</span>
                  <input
                    value={formData.quartier}
                    onChange={e => setFormData({ ...formData, quartier: e.target.value })}
                    placeholder="ex: Sidi Maârouf"
                  />
                </label>
                <label>
                  <span>Adresse E-mail</span>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={e => setFormData({ ...formData, email: e.target.value })}
                    placeholder="direction@ofppt.ma"
                  />
                </label>
                <label>
                  <span>Téléphone</span>
                  <input
                    value={formData.telephone}
                    onChange={e => setFormData({ ...formData, telephone: e.target.value })}
                    placeholder="+212 5..."
                  />
                </label>
                <label>
                  <span>Site Web</span>
                  <input
                    value={formData.site_web}
                    onChange={e => setFormData({ ...formData, site_web: e.target.value })}
                    placeholder="https://..."
                  />
                </label>
                <label>
                  <span>Couleur d'Accentuation</span>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="color"
                      value={formData.couleur_accent}
                      onChange={e => setFormData({ ...formData, couleur_accent: e.target.value })}
                      style={{ width: 40, height: 38, padding: 2, border: '1px solid #cbd5e1', borderRadius: 6, cursor: 'pointer' }}
                    />
                    <input
                      value={formData.couleur_accent}
                      onChange={e => setFormData({ ...formData, couleur_accent: e.target.value })}
                      style={{ flex: 1 }}
                    />
                  </div>
                </label>
                <label>
                  <span>Limite Formateurs</span>
                  <input
                    type="number"
                    value={formData.max_formateurs}
                    onChange={e => setFormData({ ...formData, max_formateurs: +e.target.value })}
                  />
                </label>
                <label>
                  <span>Limite Groupes</span>
                  <input
                    type="number"
                    value={formData.max_groupes}
                    onChange={e => setFormData({ ...formData, max_groupes: +e.target.value })}
                  />
                </label>
                <label className="sa-form-full">
                  <span>Adresse Physique</span>
                  <textarea
                    rows="2"
                    value={formData.adresse}
                    onChange={e => setFormData({ ...formData, adresse: e.target.value })}
                    placeholder="Adresse complète..."
                  />
                </label>
              </div>
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setShowModal(false)}>Annuler</button>
              <button className="sa-btn sa-btn--primary" onClick={handleSave}>
                {modalMode === 'create' ? 'Créer l\'Établissement' : 'Enregistrer les Modifications'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal Supprimer Établissement ─── */}
      {deletingEtab && (
        <div className="sa-modal-overlay" onClick={() => setDeletingEtab(null)}>
          <div className="sa-modal sa-modal--sm" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>Confirmer la Suppression</h2>
              <button className="sa-modal-close" onClick={() => setDeletingEtab(null)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <p style={{ margin: '0 0 12px', fontSize: '14px', color: '#1e293b' }}>
                Êtes-vous sûr de vouloir supprimer définitivement <strong>{deletingEtab.nom_court || deletingEtab.code}</strong> ?
              </p>
              <p style={{ color: '#dc2626', fontSize: '13px', margin: 0, lineHeight: 1.5 }}>
                Toutes les données associées (groupes, formateurs, affectations, salles et plannings) seront effacées de manière irréversible.
              </p>
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setDeletingEtab(null)}>Annuler</button>
              <button className="sa-btn sa-btn--danger" onClick={confirmDelete}>Supprimer Définitivement</button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal Gestion des Administrateurs (Email & Mot de passe) ─── */}
      {showAdminModal && adminEtab && (
        <div className="sa-modal-overlay" onClick={() => setShowAdminModal(false)}>
          <div className="sa-modal" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>Administrateurs — {adminEtab.nom_court || adminEtab.code}</h2>
              <button className="sa-modal-close" onClick={() => setShowAdminModal(false)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <div className="sa-form-section-title">
                <span>Comptes Administrateurs Existants ({admins.length})</span>
              </div>

              {admins.length === 0 ? (
                <p className="sa-empty">Aucun administrateur rattaché à cet établissement.</p>
              ) : (
                admins.map(a => (
                  <div key={a.id} className="sa-admin-card">
                    <div className="sa-admin-info-main">
                      <div className="sa-admin-name">
                        {a.first_name || a.last_name ? `${a.first_name} ${a.last_name}`.trim() : a.username}
                        <span style={{ marginLeft: 8, fontSize: '11px', color: '#64748b', fontWeight: 500 }}>
                          (@{a.username})
                        </span>
                      </div>
                      <div className="sa-admin-meta">
                        <span>
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                          {a.email || 'Aucun email'}
                        </span>
                        {a.date_joined && (
                          <span>
                            Créé le {new Date(a.date_joined).toLocaleDateString('fr-FR')}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="sa-actions">
                      <button
                        className="sa-btn-icon"
                        title="Modifier l'email et les informations"
                        onClick={() => setEditingAdmin({ ...a })}
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                      </button>

                      <button
                        className="sa-btn-icon sa-btn-icon--warn"
                        title="Réinitialiser / Changer le mot de passe"
                        onClick={() => {
                          setPasswordModalAdmin(a)
                          setNewAdminPassword('')
                        }}
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                      </button>

                      <button
                        className="sa-btn-icon sa-btn-icon--danger"
                        title="Supprimer ce compte administrateur"
                        onClick={() => removeAdmin(a.id)}
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                      </button>
                    </div>
                  </div>
                ))
              )}

              {/* Formulaire d'édition rapide d'un admin */}
              {editingAdmin && (
                <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, padding: 16, marginTop: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <span style={{ fontWeight: 700, fontSize: '13px', color: '#1e3a8a' }}>
                      Modifier l'administrateur : @{editingAdmin.username}
                    </span>
                    <button
                      className="sa-btn-icon"
                      style={{ padding: 2, border: 'none', background: 'transparent' }}
                      onClick={() => setEditingAdmin(null)}
                    >
                      ✕
                    </button>
                  </div>
                  <div className="sa-form-grid">
                    <label>
                      <span>Adresse E-mail</span>
                      <input
                        type="email"
                        value={editingAdmin.email || ''}
                        onChange={e => setEditingAdmin({ ...editingAdmin, email: e.target.value })}
                        placeholder="email@ofppt.ma"
                      />
                    </label>
                    <label>
                      <span>Nom d'utilisateur</span>
                      <input
                        value={editingAdmin.username || ''}
                        onChange={e => setEditingAdmin({ ...editingAdmin, username: e.target.value })}
                      />
                    </label>
                    <label>
                      <span>Prénom</span>
                      <input
                        value={editingAdmin.first_name || ''}
                        onChange={e => setEditingAdmin({ ...editingAdmin, first_name: e.target.value })}
                      />
                    </label>
                    <label>
                      <span>Nom</span>
                      <input
                        value={editingAdmin.last_name || ''}
                        onChange={e => setEditingAdmin({ ...editingAdmin, last_name: e.target.value })}
                      />
                    </label>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                    <button className="sa-btn" onClick={() => setEditingAdmin(null)}>Annuler</button>
                    <button className="sa-btn sa-btn--primary" onClick={saveEditedAdmin}>
                      Enregistrer les Modifications
                    </button>
                  </div>
                </div>
              )}

              {/* Formulaire d'ajout d'administrateur */}
              <div className="sa-form-section-title">
                <span>Créer un Nouvel Administrateur pour cet Établissement</span>
              </div>
              <div className="sa-form-grid">
                <label>
                  <span>Nom d'utilisateur (Login) *</span>
                  <input
                    value={newAdmin.username}
                    onChange={e => setNewAdmin({ ...newAdmin, username: e.target.value })}
                    placeholder="ex: admin_ntic2"
                  />
                </label>
                <label>
                  <span>Adresse E-mail *</span>
                  <input
                    type="email"
                    value={newAdmin.email}
                    onChange={e => setNewAdmin({ ...newAdmin, email: e.target.value })}
                    placeholder="admin@ofppt-ntic.ma"
                  />
                </label>
                <label>
                  <span>Mot de Passe Initial *</span>
                  <input
                    type="password"
                    value={newAdmin.password}
                    onChange={e => setNewAdmin({ ...newAdmin, password: e.target.value })}
                    placeholder="Mot de passe sécurisé"
                  />
                </label>
                <label>
                  <span>Prénom</span>
                  <input
                    value={newAdmin.first_name}
                    onChange={e => setNewAdmin({ ...newAdmin, first_name: e.target.value })}
                    placeholder="ex: Mohammed"
                  />
                </label>
                <label className="sa-form-full">
                  <span>Nom</span>
                  <input
                    value={newAdmin.last_name}
                    onChange={e => setNewAdmin({ ...newAdmin, last_name: e.target.value })}
                    placeholder="ex: Alami"
                  />
                </label>
              </div>
              <div style={{ marginTop: 14 }}>
                <button className="sa-btn sa-btn--primary" onClick={addAdmin}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  <span>Créer le Compte Administrateur</span>
                </button>
              </div>
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setShowAdminModal(false)}>Fermer</button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal Modification du Mot de Passe Admin ─── */}
      {passwordModalAdmin && (
        <div className="sa-modal-overlay" onClick={() => setPasswordModalAdmin(null)}>
          <div className="sa-modal sa-modal--sm" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>Changer le Mot de Passe</h2>
              <button className="sa-modal-close" onClick={() => setPasswordModalAdmin(null)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <p style={{ margin: '0 0 14px', fontSize: '13.5px', color: '#334155' }}>
                Définissez un nouveau mot de passe pour l'administrateur <strong>@{passwordModalAdmin.username}</strong> ({passwordModalAdmin.email || 'Sans email'}).
              </p>
              <div className="sa-form-grid" style={{ gridTemplateColumns: '1fr' }}>
                <label>
                  <span>Nouveau Mot de Passe *</span>
                  <input
                    type="password"
                    value={newAdminPassword}
                    onChange={e => setNewAdminPassword(e.target.value)}
                    placeholder="Saisir le nouveau mot de passe..."
                    autoFocus
                  />
                </label>
              </div>
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setPasswordModalAdmin(null)}>Annuler</button>
              <button className="sa-btn sa-btn--primary" onClick={saveNewAdminPassword}>
                Mettre à Jour le Mot de Passe
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Modal Statistiques Détail Établissement ─── */}
      {detailEtab && (
        <div className="sa-modal-overlay" onClick={() => setDetailEtab(null)}>
          <div className="sa-modal" onClick={e => e.stopPropagation()}>
            <div className="sa-modal-header">
              <h2>Statistiques — {detailEtab.etablissement?.nom_court || detailEtab.etablissement?.code}</h2>
              <button className="sa-modal-close" onClick={() => setDetailEtab(null)}>✕</button>
            </div>
            <div className="sa-modal-body">
              <div className="sa-stats-grid sa-stats-grid--compact">
                <div className="sa-stat-card">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_formateurs}</div>
                    <div className="sa-stat-label">Total Formateurs</div>
                  </div>
                </div>
                <div className="sa-stat-card sa-stat-card--green">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_formateurs_permanents}</div>
                    <div className="sa-stat-label">Permanents</div>
                  </div>
                </div>
                <div className="sa-stat-card sa-stat-card--amber">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_formateurs_vacataires}</div>
                    <div className="sa-stat-label">Vacataires</div>
                  </div>
                </div>
                <div className="sa-stat-card">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_groupes}</div>
                    <div className="sa-stat-label">Groupes</div>
                  </div>
                </div>
                <div className="sa-stat-card">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_salles}</div>
                    <div className="sa-stat-label">Total Salles</div>
                  </div>
                </div>
                <div className="sa-stat-card sa-stat-card--green">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_salles_actives}</div>
                    <div className="sa-stat-label">Salles Actives</div>
                  </div>
                </div>
                <div className="sa-stat-card">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_modules}</div>
                    <div className="sa-stat-label">Modules</div>
                  </div>
                </div>
                <div className="sa-stat-card">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_secteurs}</div>
                    <div className="sa-stat-label">Secteurs</div>
                  </div>
                </div>
                <div className="sa-stat-card">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_admins}</div>
                    <div className="sa-stat-label">Admins Établissement</div>
                  </div>
                </div>
                <div className="sa-stat-card">
                  <div>
                    <div className="sa-stat-value">{detailEtab.nb_utilisateurs}</div>
                    <div className="sa-stat-label">Total Utilisateurs</div>
                  </div>
                </div>
              </div>
            </div>
            <div className="sa-modal-footer">
              <button className="sa-btn" onClick={() => setDetailEtab(null)}>Fermer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
