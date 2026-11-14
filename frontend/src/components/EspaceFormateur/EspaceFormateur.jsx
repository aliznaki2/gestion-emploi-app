import { useEffect, useMemo, useState } from 'react'
import { APP_NAME, useInstitute } from '../../config/branding'
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

const PAGES = [
  { id: 'accueil', label: 'Accueil' },
  { id: 'disponibilites', label: 'Mes disponibilités' },
  { id: 'emploi', label: 'Mon emploi du temps' },
  { id: 'affectations', label: 'Mes affectations' },
  { id: 'profil', label: 'Mon Profil' },
]

const STATUTS_PROFIL = [
  { id: 'permanent', label: 'Permanent' },
  { id: 'vacataire', label: 'Vacataire' },
]

const STATUTS_DEMANDE = {
  en_attente: 'En attente',
  approuvee: 'Approuvée',
  refusee: 'Refusée',
}

const CHAMPS_PROFIL = {
  email: 'Email',
  telephone: 'Téléphone',
  statut: 'Statut',
  heures_max_semaine: 'Heures max / semaine',
  salle_preferee_id: 'Salle préférée',
  salle_preferee_matin_id: 'Salle préférée (matin)',
  salle_preferee_apm_id: 'Salle préférée (après-midi)',
}

const formProfilVide = {
  email: '',
  telephone: '',
  statut: 'permanent',
  heures_max_semaine: 30,
  salle_preferee_id: '',
  salle_preferee_matin_id: '',
  salle_preferee_apm_id: '',
}

const ETATS = ['disponible', 'bloque', 'prefere']
const CYCLE_ETATS = { disponible: 'bloque', bloque: 'prefere', prefere: 'disponible' }
const LIBELLES_ETATS = {
  disponible: 'Disponible',
  bloque: 'Indisponible',
  prefere: '★ Préféré',
}

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

const heureEnMinutes = (valeur) => {
  const [h, m] = String(valeur || '').split(':').map(Number)
  return (h || 0) * 60 + (m || 0)
}

const pad2 = (n) => String(n).padStart(2, '0')

const icsDate = (date) =>
  `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}` +
  `T${pad2(date.getHours())}${pad2(date.getMinutes())}00`

const echapperICS = (valeur) =>
  String(valeur || '')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n')

const SemaineSelect = ({ semaines, semaine, onChange }) => (
  <label className="ef-week">
    <span>Semaine</span>
    <select
      value={semaine?.id || ''}
      onChange={(e) =>
        onChange(semaines.find((s) => String(s.id) === e.target.value) || null)
      }
    >
      {semaines.map((s) => (
        <option key={s.id} value={s.id}>
          Semaine {s.numero}
          {s.date_debut ? ` (${formatDate(s.date_debut)} au ${formatDate(s.date_fin)})` : ''}
        </option>
      ))}
    </select>
  </label>
)

/**
 * Espace du profil « formateur ».
 *
 * Cinq pages :
 *  - Accueil : résumé de la charge, disponibilités et prochaine séance.
 *  - Mes disponibilités : grille hebdomadaire disponible / préféré / indisponible.
 *  - Mon emploi du temps : planning personnel, impression et export iCalendar.
 *  - Mes affectations : modules et groupes attribués au formateur.
 *  - Mon Profil : fiche personnelle et demandes de modification validées par l'administration.
 */
export default function EspaceFormateur({ email = '', onLogout }) {
  const [institute] = useInstitute()
  const [activePage, setActivePage] = useState('accueil')

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

  const [affectations, setAffectations] = useState([])
  const [loadingAffectations, setLoadingAffectations] = useState(false)
  const [affectationsError, setAffectationsError] = useState('')

  const [initialError, setInitialError] = useState('')

  const [salles, setSalles] = useState([])
  const [demandesProfil, setDemandesProfil] = useState([])
  const [loadingDemandes, setLoadingDemandes] = useState(false)
  const [demandesError, setDemandesError] = useState('')
  const [profilForm, setProfilForm] = useState(formProfilVide)
  const [profilCommentaire, setProfilCommentaire] = useState('')
  const [savingProfil, setSavingProfil] = useState(false)
  const [profilMessage, setProfilMessage] = useState('')
  const [profilError, setProfilError] = useState('')

  // ── Chargement initial : profils, créneaux, semaines ─────────────────────
  useEffect(() => {
    let actif = true

    Promise.all([
      apiFetch(`${API}/professeurs`).catch(() => []),
      apiFetch(`${API}/creneaux`).catch(() => []),
      apiFetch(`${API}/semaines`).catch(() => []),
      apiFetch(`${API}/salles`).catch(() => []),
    ])
      .then(([profs, crs, sems, sls]) => {
        if (!actif) return
        setProfesseurs(profs)
        setCreneaux(crs)
        setSemaines(sems)
        setSalles(Array.isArray(sls) ? sls : [])
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
    setProfilMessage('')
    setProfilError('')
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

  // ── Affectations du formateur sélectionné ────────────────────────────────
  useEffect(() => {
    if (!profId) {
      setAffectations([])
      return
    }
    let actif = true
    setLoadingAffectations(true)
    setAffectationsError('')

    apiFetch(`${API}/affectations?professeur_id=${profId}`)
      .then((liste) => {
        if (actif) setAffectations(Array.isArray(liste) ? liste : [])
      })
      .catch((err) => {
        if (actif) {
          setAffectations([])
          setAffectationsError(err.message || 'Impossible de charger les affectations.')
        }
      })
      .finally(() => {
        if (actif) setLoadingAffectations(false)
      })

    return () => {
      actif = false
    }
  }, [profId])

  // ── Demandes de modification de profil ───────────────────────────────────
  useEffect(() => {
    if (!profId) {
      setDemandesProfil([])
      return
    }
    let actif = true
    setLoadingDemandes(true)
    setDemandesError('')

    apiFetch(`${API}/demandes-profil?professeur_id=${profId}`)
      .then((liste) => {
        if (actif) setDemandesProfil(Array.isArray(liste) ? liste : [])
      })
      .catch((err) => {
        if (actif) {
          setDemandesProfil([])
          setDemandesError(err.message || 'Impossible de charger vos demandes.')
        }
      })
      .finally(() => {
        if (actif) setLoadingDemandes(false)
      })

    return () => {
      actif = false
    }
  }, [profId])

  const demandeEnAttente = useMemo(
    () => demandesProfil.find((d) => d.statut === 'en_attente') || null,
    [demandesProfil],
  )

  // Pré-remplit le formulaire avec la fiche actuelle (ou la demande en attente).
  useEffect(() => {
    if (!profSelectionne) {
      setProfilForm(formProfilVide)
      setProfilCommentaire('')
      return
    }
    const source = demandeEnAttente
      ? { ...profSelectionne, ...(demandeEnAttente.donnees || {}) }
      : profSelectionne
    const salleId = (valeur) => (valeur ? String(valeur) : '')
    setProfilForm({
      email: source.email || '',
      telephone: source.telephone || '',
      statut: source.statut || 'permanent',
      heures_max_semaine: source.heures_max_semaine ?? 30,
      salle_preferee_id: salleId(source.salle_preferee_id),
      salle_preferee_matin_id: salleId(source.salle_preferee_matin_id),
      salle_preferee_apm_id: salleId(source.salle_preferee_apm_id),
    })
    setProfilCommentaire(demandeEnAttente?.commentaire_formateur || '')
  }, [profSelectionne, demandeEnAttente])

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

  const hoursMax = Number(profSelectionne?.heures_max_semaine) || 0
  const pctCharge = hoursMax > 0 ? Math.min(100, (statsSemaine.heures / hoursMax) * 100) : 0
  const surcharge = hoursMax > 0 && statsSemaine.heures > hoursMax

  const chargeTheorique = useMemo(
    () =>
      affectations.reduce((total, a) => total + (Number(a.module_heures) || 0), 0),
    [affectations],
  )

  const nbDispo = useMemo(
    () => creneaux.filter((c) => (dispos[c.id] || 'disponible') !== 'bloque').length,
    [creneaux, dispos],
  )
  const nbPref = useMemo(
    () => creneaux.filter((c) => dispos[c.id] === 'prefere').length,
    [creneaux, dispos],
  )
  const nbBloques = creneaux.length - nbDispo
  const capaciteDispoH = nbDispo * 2.5
  const alerteDispo =
    creneaux.length > 0 && chargeTheorique > 0 && capaciteDispoH < chargeTheorique

  const prochaineSeance = useMemo(() => {
    if (!mesSeances.length) return { seance: null, label: 'Aucune séance planifiée' }
    const triees = [...mesSeances].sort(
      (a, b) => a.jour - b.jour || a.numero_seance - b.numero_seance,
    )
    const debut = selectedSemaine?.date_debut
      ? new Date(`${selectedSemaine.date_debut}T00:00:00`)
      : null
    const fin = selectedSemaine?.date_fin
      ? new Date(`${selectedSemaine.date_fin}T23:59:59`)
      : null
    const maintenant = new Date()
    if (debut && fin && maintenant >= debut && maintenant <= fin) {
      const jourCourant = maintenant.getDay() === 0 ? 7 : maintenant.getDay()
      const minutes = maintenant.getHours() * 60 + maintenant.getMinutes()
      const suivante = triees.find((s) => {
        if (s.jour > jourCourant) return true
        if (s.jour < jourCourant) return false
        return heureEnMinutes(s.heure_debut) >= minutes
      })
      if (suivante) return { seance: suivante, label: 'Prochaine séance' }
    }
    return { seance: triees[0], label: 'Première séance de la semaine' }
  }, [mesSeances, selectedSemaine])

  const affectationsTriees = useMemo(
    () =>
      [...affectations].sort(
        (a, b) =>
          String(a.groupe_code).localeCompare(String(b.groupe_code)) ||
          String(a.module_code).localeCompare(String(b.module_code)),
      ),
    [affectations],
  )

  const seancesParAffectation = useMemo(() => {
    const map = {}
    mesSeances.forEach((s) => {
      ;(s.groupes || []).forEach((g) => {
        const cle = `${s.module_code}|${g.groupe_code}`
        map[cle] = (map[cle] || 0) + 1
      })
    })
    return map
  }, [mesSeances])

  const nbGroupesAffectes = useMemo(
    () => new Set(affectations.map((a) => a.groupe_id)).size,
    [affectations],
  )
  const nbModulesAffectes = useMemo(
    () => new Set(affectations.map((a) => a.module_id)).size,
    [affectations],
  )

  const etatCreneau = (creneauId) => {
    const etat = dispos[creneauId]
    return ETATS.includes(etat) ? etat : 'disponible'
  }

  const basculerCreneau = (creneauId) => {
    setDispos((prev) => ({
      ...prev,
      [creneauId]: CYCLE_ETATS[ETATS.includes(prev[creneauId]) ? prev[creneauId] : 'disponible'],
    }))
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

  const nomSalle = (id) => {
    if (!id) return 'Aucune'
    const salle = salles.find((s) => String(s.id) === String(id))
    return salle?.nom || `Salle #${id}`
  }

  const valeurAffichee = (cle, valeur) => {
    if (cle.startsWith('salle_')) return nomSalle(valeur)
    if (cle === 'heures_max_semaine') {
      return valeur === null || valeur === undefined || valeur === '' ? '—' : `${valeur} h`
    }
    if (cle === 'statut') return valeur === 'vacataire' ? 'Vacataire' : 'Permanent'
    return valeur || '—'
  }

  const changementsDemande = (demande) => {
    const donnees = demande?.donnees || {}
    const actuel = demande?.actuel || {}
    return Object.entries(donnees)
      .map(([cle, apres]) => ({
        cle,
        label: CHAMPS_PROFIL[cle] || cle,
        avant: valeurAffichee(cle, actuel[cle]),
        apres: valeurAffichee(cle, apres),
      }))
      .filter((changement) => changement.avant !== changement.apres)
  }

  const modifierChampProfil = (champ, valeur) => {
    setProfilForm((prev) => ({ ...prev, [champ]: valeur }))
    setProfilMessage('')
    setProfilError('')
  }

  const envoyerDemandeProfil = async (event) => {
    event.preventDefault()
    if (!profId) return
    setSavingProfil(true)
    setProfilError('')
    setProfilMessage('')
    try {
      const demande = await apiFetch(`${API}/demandes-profil`, {
        method: 'POST',
        body: JSON.stringify({
          professeur_id: Number(profId),
          email: profilForm.email.trim(),
          telephone: profilForm.telephone.trim(),
          statut: profilForm.statut,
          heures_max_semaine: Number(profilForm.heures_max_semaine) || 0,
          salle_preferee_id: profilForm.salle_preferee_id || null,
          salle_preferee_matin_id: profilForm.salle_preferee_matin_id || null,
          salle_preferee_apm_id: profilForm.salle_preferee_apm_id || null,
          commentaire_formateur: profilCommentaire.trim(),
        }),
      })
      setDemandesProfil((prev) => [
        demande,
        ...prev.filter((d) => d.id !== demande.id),
      ])
      setProfilMessage(
        "Votre demande a été envoyée. Elle sera appliquée après validation par l'administration.",
      )
    } catch (err) {
      setProfilError(err.message || "Impossible d'envoyer la demande.")
    } finally {
      setSavingProfil(false)
    }
  }

  const annulerDemandeProfil = async () => {
    if (!demandeEnAttente) return
    setSavingProfil(true)
    setProfilError('')
    setProfilMessage('')
    try {
      await apiFetch(`${API}/demandes-profil/${demandeEnAttente.id}`, { method: 'DELETE' })
      setDemandesProfil((prev) => prev.filter((d) => d.id !== demandeEnAttente.id))
      setProfilMessage('Votre demande a été annulée.')
    } catch (err) {
      setProfilError(err.message || "Impossible d'annuler la demande.")
    } finally {
      setSavingProfil(false)
    }
  }

  const imprimer = () => {
    if (typeof window !== 'undefined') window.print()
  }

  const exporterICS = () => {
    if (!mesSeances.length || !profSelectionne) return
    const base = selectedSemaine?.date_debut
      ? new Date(`${selectedSemaine.date_debut}T12:00:00`)
      : null
    const maintenant = new Date()
    const dtstamp =
      `${maintenant.getUTCFullYear()}${pad2(maintenant.getUTCMonth() + 1)}` +
      `${pad2(maintenant.getUTCDate())}T${pad2(maintenant.getUTCHours())}` +
      `${pad2(maintenant.getUTCMinutes())}${pad2(maintenant.getUTCSeconds())}Z`

    const lignes = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//GestEmploi//Espace formateur//FR',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
    ]

    mesSeances.forEach((s) => {
      const [debutH, debutM] = String(s.heure_debut || '').split(':').map(Number)
      const [finH, finM] = String(s.heure_fin || '').split(':').map(Number)
      lignes.push('BEGIN:VEVENT')
      lignes.push(`UID:seance-${s.id}@gestemploi`)
      lignes.push(`DTSTAMP:${dtstamp}`)
      if (base) {
        const jour = new Date(base)
        jour.setDate(base.getDate() + (Number(s.jour) - 1))
        const debut = new Date(jour)
        debut.setHours(debutH || 0, debutM || 0, 0, 0)
        const fin = new Date(jour)
        fin.setHours(finH || 0, finM || 0, 0, 0)
        lignes.push(`DTSTART:${icsDate(debut)}`)
        lignes.push(`DTEND:${icsDate(fin)}`)
      }
      lignes.push(`SUMMARY:${echapperICS(`${s.module_code} — ${s.module_intitule}`)}`)
      lignes.push(`LOCATION:${echapperICS(s.salle_nom || '')}`)
      const groupes = (s.groupes || []).map((g) => g.groupe_code).join(', ')
      lignes.push(
        `DESCRIPTION:${echapperICS(
          `Groupe(s) : ${groupes} · Formateur : ${profSelectionne.nom_complet}`,
        )}`,
      )
      lignes.push('END:VEVENT')
    })

    lignes.push('END:VCALENDAR')

    const blob = new Blob([lignes.join('\r\n') + '\r\n'], {
      type: 'text/calendar;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const lien = document.createElement('a')
    lien.href = url
    lien.download =
      `emploi-du-temps-${profSelectionne.nom_complet
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-zA-Z0-9]+/g, '-')
        .toLowerCase()}-semaine-${selectedSemaine?.numero || ''}.ics`
    document.body.appendChild(lien)
    lien.click()
    lien.remove()
    URL.revokeObjectURL(url)
  }

  const semaineLabel = selectedSemaine?.date_debut
    ? `Semaine ${selectedSemaine.numero} · du ${formatDate(selectedSemaine.date_debut)} au ${formatDate(selectedSemaine.date_fin)}`
    : selectedSemaine
      ? `Semaine ${selectedSemaine.numero}`
      : ''

  return (
    <div className="espace-formateur">
      <header className="espace-formateur__topbar">
        <div className="espace-formateur__brand">
          <h1>{APP_NAME}</h1>
          <span>{institute.name} · {institute.district}</span>
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
        {PAGES.map((page) => (
          <button
            key={page.id}
            type="button"
            className={`ef-tab ${activePage === page.id ? 'active' : ''}`}
            onClick={() => setActivePage(page.id)}
          >
            {page.label}
          </button>
        ))}
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

        {activePage === 'accueil' && (
          <section className="ef-card">
            <div className="ef-hello">
              <div>
                <p className="ef-eyebrow">Espace formateur</p>
                <h2>Bonjour, {profSelectionne?.nom_complet || 'Formateur'}</h2>
                <p className="ef-hello-sub">
                  {profSelectionne?.statut === 'vacataire' ? 'Vacataire' : 'Permanent'}
                  {profSelectionne?.matricule ? ` · ${profSelectionne.matricule}` : ''}
                  {semaineLabel ? ` · ${semaineLabel}` : ''}
                </p>
              </div>
              {semaines.length > 0 && (
                <div className="ef-head-actions ef-no-print">
                  <SemaineSelect
                    semaines={semaines}
                    semaine={selectedSemaine}
                    onChange={setSelectedSemaine}
                  />
                </div>
              )}
            </div>

            <div className="ef-kpis">
              <article className="ef-kpi">
                <span className="ef-kpi-label">Heures planifiées</span>
                <span className="ef-kpi-value">{statsSemaine.heures} h</span>
                <span className="ef-kpi-sub">
                  {hoursMax > 0 ? `sur ${hoursMax} h autorisées` : 'aucun plafond défini'}
                </span>
                {hoursMax > 0 && (
                  <div className="ef-progress">
                    <div
                      className={`ef-progress-fill ${surcharge ? 'ef-progress-fill--over' : ''}`}
                      style={{ width: `${pctCharge}%` }}
                    />
                  </div>
                )}
              </article>

              <article className="ef-kpi">
                <span className="ef-kpi-label">Séances</span>
                <span className="ef-kpi-value">{statsSemaine.seances}</span>
                <span className="ef-kpi-sub">
                  {statsSemaine.groupes} groupe{statsSemaine.groupes > 1 ? 's' : ''} ·{' '}
                  {statsSemaine.modules} module{statsSemaine.modules > 1 ? 's' : ''}
                </span>
              </article>

              <article className="ef-kpi">
                <span className="ef-kpi-label">Disponibilités</span>
                <span className="ef-kpi-value">
                  {nbDispo} / {creneaux.length}
                </span>
                <span className="ef-kpi-sub">
                  {nbBloques} indispo · {nbPref} préféré{nbPref > 1 ? 's' : ''}
                </span>
              </article>

              <article className="ef-kpi">
                <span className="ef-kpi-label">Charge théorique</span>
                <span className="ef-kpi-value">{chargeTheorique} h</span>
                <span className="ef-kpi-sub">
                  {affectations.length} affectation{affectations.length > 1 ? 's' : ''}
                </span>
              </article>
            </div>

            {surcharge && (
              <div className="ef-alert ef-alert--error">
                Votre emploi du temps dépasse votre volume maximal de{' '}
                <strong>{hoursMax} h</strong> ({statsSemaine.heures} h planifiées).
                Contactez l'administration si nécessaire.
              </div>
            )}

            {alerteDispo && (
              <div className="ef-alert ef-alert--info">
                Vos disponibilités couvrent environ <strong>{capaciteDispoH} h</strong>{' '}
                ({nbDispo} créneaux) pour une charge théorique de{' '}
                <strong>{chargeTheorique} h</strong>. Pensez à libérer des créneaux.
              </div>
            )}

            {affectations.length === 0 && mesSeances.length > 0 && (
              <div className="ef-alert ef-alert--info">
                Votre emploi du temps contient des séances, mais aucune affectation
                n'est enregistrée pour l'année en cours. Contactez l'administration
                pour régulariser votre fiche.
              </div>
            )}

            <div className="ef-overview-grid">
              <div className="ef-overview-block">
                <h3>{prochaineSeance.seance ? prochaineSeance.label : 'Prochaine séance'}</h3>
                {loadingSeances ? (
                  <div className="ef-empty">Chargement de votre emploi du temps…</div>
                ) : prochaineSeance.seance ? (
                  <div className="ef-next">
                    <div className="ef-next-when">
                      <span className="ef-next-day">
                        {JOURS.find((j) => j.id === prochaineSeance.seance.jour)?.nom}
                      </span>
                      <span className="ef-next-time">
                        {horaire(prochaineSeance.seance)}
                      </span>
                    </div>
                    <div className="ef-next-body">
                      <strong>
                        {prochaineSeance.seance.module_code} ·{' '}
                        {prochaineSeance.seance.module_intitule}
                      </strong>
                      <span>
                        {(prochaineSeance.seance.groupes || [])
                          .map((g) => g.groupe_code)
                          .join(', ')}
                      </span>
                      <span>{prochaineSeance.seance.salle_nom || 'Salle à définir'}</span>
                    </div>
                  </div>
                ) : (
                  <div className="ef-empty">
                    <strong>Aucune séance cette semaine</strong>
                    <span>Votre emploi du temps apparaîtra ici dès qu'il sera publié.</span>
                  </div>
                )}
                <div className="ef-quick-links">
                  <button
                    type="button"
                    className="ef-link-btn"
                    onClick={() => setActivePage('emploi')}
                  >
                    Voir mon emploi du temps →
                  </button>
                  <button
                    type="button"
                    className="ef-link-btn"
                    onClick={() => setActivePage('disponibilites')}
                  >
                    Ajuster mes disponibilités →
                  </button>
                </div>
              </div>

              <div className="ef-overview-block">
                <h3>Mes affectations</h3>
                {loadingAffectations ? (
                  <div className="ef-empty">Chargement de vos affectations…</div>
                ) : affectationsTriees.length === 0 ? (
                  <div className="ef-empty">
                    <strong>Aucune affectation</strong>
                    <span>
                      Vos modules et groupes apparaîtront ici dès que l'administration
                      les aura saisis.
                    </span>
                  </div>
                ) : (
                  <ul className="ef-mini-list">
                    {affectationsTriees.slice(0, 5).map((a) => (
                      <li key={a.id} className="ef-mini-item">
                        <span className="ef-mini-group">{a.groupe_code}</span>
                        <span className="ef-mini-module">
                          {a.module_code} · {a.module_intitule}
                        </span>
                        <span className="ef-mini-hours">{a.module_heures} h</span>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="ef-quick-links">
                  <button
                    type="button"
                    className="ef-link-btn"
                    onClick={() => setActivePage('affectations')}
                  >
                    Toutes mes affectations →
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}

        {activePage === 'disponibilites' && (
          <section className="ef-card">
            <div className="ef-card-head">
              <div>
                <h2>Mes disponibilités</h2>
                <p>
                  Indiquez les créneaux où vous êtes disponible pour enseigner.
                  Les créneaux <strong>Indisponible</strong> sont évités par le
                  moteur, et les créneaux <strong>Préféré</strong> sont favorisés
                  lors de la génération.
                </p>
              </div>
              {profSelectionne && (
                <span className="ef-prof-badge">{profSelectionne.nom_complet}</span>
              )}
            </div>

            <div className="ef-legend">
              <span><i className="ef-dot ef-dot--ok" /> Disponible</span>
              <span><i className="ef-dot ef-dot--pref" /> Préféré</span>
              <span><i className="ef-dot ef-dot--off" /> Indisponible</span>
              <span className="ef-legend-hint">
                Cliquez sur un créneau : Disponible → Indisponible → Préféré.
              </span>
            </div>

            <div className="ef-availability-stats">
              <span><strong>{nbDispo}</strong> disponibles</span>
              <span><strong>{nbPref}</strong> préféré{nbPref > 1 ? 's' : ''}</span>
              <span><strong>{nbBloques}</strong> indisponible{nbBloques > 1 ? 's' : ''}</span>
              <span><strong>{nbDispo * 2.5} h</strong> de capacité</span>
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
                                title={`${jour.nom} ${horaire(creneau)} — ${LIBELLES_ETATS[etat]}`}
                              >
                                <span className="ef-slot-label">
                                  {LIBELLES_ETATS[etat]}
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
            <div className="ef-print-only ef-print-head">
              <h1>Emploi du temps</h1>
              <p>
                {profSelectionne?.nom_complet}
                {profSelectionne?.matricule ? ` (${profSelectionne.matricule})` : ''}
                {semaineLabel ? ` · ${semaineLabel}` : ''}
              </p>
            </div>

            <div className="ef-card-head">
              <div>
                <h2>Mon emploi du temps</h2>
                <p>
                  Vos séances pour la semaine sélectionnée, avec le groupe, le
                  module et la salle.
                </p>
              </div>
              <div className="ef-head-actions ef-no-print">
                {semaines.length > 0 && (
                  <SemaineSelect
                    semaines={semaines}
                    semaine={selectedSemaine}
                    onChange={setSelectedSemaine}
                  />
                )}
                <button
                  type="button"
                  className="ef-btn ef-btn--ghost"
                  onClick={imprimer}
                  disabled={!mesSeances.length}
                >
                  Imprimer
                </button>
                <button
                  type="button"
                  className="ef-btn ef-btn--ghost"
                  onClick={exporterICS}
                  disabled={!mesSeances.length}
                >
                  Exporter (.ics)
                </button>
              </div>
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
                <span className="ef-period">{semaineLabel}</span>
              </div>
            )}
          </section>
        )}

        {activePage === 'affectations' && (
          <section className="ef-card">
            <div className="ef-card-head">
              <div>
                <h2>Mes affectations</h2>
                <p>
                  Les modules et groupes qui vous sont affectés. Les heures
                  indiquées correspondent au volume hebdomadaire prévu.
                </p>
              </div>
              {profSelectionne && (
                <span className="ef-prof-badge">{profSelectionne.nom_complet}</span>
              )}
            </div>

            {affectationsError && (
              <div className="ef-alert ef-alert--error">{affectationsError}</div>
            )}

            <div className="ef-summary">
              <span><strong>{affectations.length}</strong> affectation{affectations.length > 1 ? 's' : ''}</span>
              <span><strong>{nbGroupesAffectes}</strong> groupe{nbGroupesAffectes > 1 ? 's' : ''}</span>
              <span><strong>{nbModulesAffectes}</strong> module{nbModulesAffectes > 1 ? 's' : ''}</span>
              <span><strong>{chargeTheorique}</strong> h / semaine</span>
            </div>

            {loadingAffectations ? (
              <div className="ef-empty">Chargement de vos affectations…</div>
            ) : affectationsTriees.length === 0 ? (
              <div className="ef-empty">
                <strong>Aucune affectation enregistrée</strong>
                <span>
                  Vos modules et groupes apparaîtront ici dès que l'administration
                  les aura saisis.
                </span>
              </div>
            ) : (
              <div className="ef-table-wrap">
                <table className="ef-table">
                  <thead>
                    <tr>
                      <th>Groupe</th>
                      <th>Filière</th>
                      <th>Module</th>
                      <th>Intitulé</th>
                      <th className="ef-table-num">Heures / sem.</th>
                      <th className="ef-table-num">Séances cette semaine</th>
                    </tr>
                  </thead>
                  <tbody>
                    {affectationsTriees.map((a) => {
                      const nbSeances =
                        seancesParAffectation[`${a.module_code}|${a.groupe_code}`] || 0
                      return (
                        <tr key={a.id}>
                          <td><span className="ef-table-strong">{a.groupe_code}</span></td>
                          <td>{a.filiere_code || '—'}</td>
                          <td><span className="ef-table-module">{a.module_code}</span></td>
                          <td>{a.module_intitule}</td>
                          <td className="ef-table-num">{a.module_heures} h</td>
                          <td className="ef-table-num">
                            <span className={`ef-count ${nbSeances ? '' : 'ef-count--zero'}`}>
                              {nbSeances}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {activePage === 'profil' && (
          <div className="ef-profile-page">
            <section className="ef-profile-hero">
              {profSelectionne ? (
                <>
                  <div className="ef-profile-avatar" aria-hidden="true">
                    {(profSelectionne.nom_complet || '')
                      .split(/\s+/)
                      .filter(Boolean)
                      .slice(0, 2)
                      .map((mot) => mot[0].toUpperCase())
                      .join('')}
                  </div>
                  <div className="ef-profile-identity">
                    <p className="ef-eyebrow">Mon profil</p>
                    <h2>{profSelectionne.nom_complet}</h2>
                    <div className="ef-profile-tags">
                      <span className="ef-profile-tag">
                        Matricule {profSelectionne.matricule || '—'}
                      </span>
                      <span
                        className={`ef-status-badge ${
                          profSelectionne.statut === 'vacataire'
                            ? 'ef-status-badge--vacataire'
                            : ''
                        }`}
                      >
                        {profSelectionne.statut === 'vacataire' ? 'Vacataire' : 'Permanent'}
                      </span>
                    </div>
                  </div>
                  <div className="ef-profile-hero-stats">
                    <div>
                      <strong>{affectations.length}</strong>
                      <span>affectation{affectations.length > 1 ? 's' : ''}</span>
                    </div>
                    <div>
                      <strong>{chargeTheorique} h</strong>
                      <span>charge / semaine</span>
                    </div>
                    <div>
                      <strong>{hoursMax ? `${hoursMax} h` : '—'}</strong>
                      <span>plafond hebdo</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="ef-profile-identity">
                  <p className="ef-eyebrow">Mon profil</p>
                  <h2>Aucun profil sélectionné</h2>
                  <p>Choisissez votre profil dans la liste en haut de la page.</p>
                </div>
              )}
            </section>

            {demandesError && <div className="ef-alert ef-alert--error">{demandesError}</div>}
            {profilError && <div className="ef-alert ef-alert--error">{profilError}</div>}
            {profilMessage && <div className="ef-alert ef-alert--success">{profilMessage}</div>}

            {profSelectionne && (
              <>
                <div className="ef-profile-layout">
                  <div className="ef-profile-col">
                    <section className="ef-panel">
                      <header className="ef-panel-head">
                        <h3>Ma fiche</h3>
                        <span className="ef-panel-hint">Lecture seule</span>
                      </header>
                      <dl className="ef-facts">
                        <div>
                          <dt>Matricule</dt>
                          <dd>{profSelectionne.matricule || '—'}</dd>
                        </div>
                        <div>
                          <dt>Email</dt>
                          <dd>{profSelectionne.email || 'Non renseigné'}</dd>
                        </div>
                        <div>
                          <dt>Téléphone</dt>
                          <dd>{profSelectionne.telephone || 'Non renseigné'}</dd>
                        </div>
                      </dl>

                      <div className="ef-fiche-block">
                        <span className="ef-fiche-label">Modules</span>
                        {(profSelectionne.modules || []).length === 0 ? (
                          <span className="ef-muted">Aucun module affecté.</span>
                        ) : (
                          <div className="ef-module-chips">
                            {profSelectionne.modules.map((module) => (
                              <span key={module.id} className="ef-module-chip">
                                {module.code}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="ef-fiche-block">
                        <span className="ef-fiche-label">Affectations</span>
                        <p className="ef-fiche-line">
                          <strong>{affectations.length}</strong> affectation
                          {affectations.length > 1 ? 's' : ''} ·{' '}
                          <strong>{chargeTheorique} h</strong> / semaine
                        </p>
                      </div>
                    </section>

                    <section className="ef-panel">
                      <header className="ef-panel-head">
                        <h3>Préférences actuelles</h3>
                        <span className="ef-panel-hint">Via une demande</span>
                      </header>
                      <dl className="ef-facts">
                        <div>
                          <dt>Heures max / semaine</dt>
                          <dd>{hoursMax ? `${hoursMax} h` : '—'}</dd>
                        </div>
                        <div>
                          <dt>Salle générale</dt>
                          <dd>{nomSalle(profSelectionne.salle_preferee_id)}</dd>
                        </div>
                        <div>
                          <dt>Salle matin</dt>
                          <dd>{nomSalle(profSelectionne.salle_preferee_matin_id)}</dd>
                        </div>
                        <div>
                          <dt>Salle après-midi</dt>
                          <dd>{nomSalle(profSelectionne.salle_preferee_apm_id)}</dd>
                        </div>
                      </dl>
                    </section>
                  </div>

                  <div className="ef-profile-col">
                    {demandeEnAttente && (
                      <section className="ef-pending">
                        <div className="ef-pending-head">
                          <div>
                            <h3>Demande en attente de validation</h3>
                            <p>
                              Envoyée le {formatDate(demandeEnAttente.date_demande)}. Vous
                              pouvez encore la mettre à jour ou l'annuler.
                            </p>
                          </div>
                          <span className="ef-demande-badge ef-demande-badge--en_attente">
                            En attente
                          </span>
                        </div>
                        <ul className="ef-change-list">
                          {changementsDemande(demandeEnAttente).map((changement) => (
                            <li key={changement.cle}>
                              <span className="ef-change-label">{changement.label}</span>
                              <span className="ef-change-old">{changement.avant}</span>
                              <span className="ef-change-arrow">→</span>
                              <span className="ef-change-new">{changement.apres}</span>
                            </li>
                          ))}
                        </ul>
                        {demandeEnAttente.commentaire_formateur && (
                          <p className="ef-pending-motif">
                            <strong>Motif :</strong>{' '}
                            {demandeEnAttente.commentaire_formateur}
                          </p>
                        )}
                        <button
                          type="button"
                          className="ef-btn ef-btn--ghost"
                          onClick={annulerDemandeProfil}
                          disabled={savingProfil}
                        >
                          Annuler la demande
                        </button>
                      </section>
                    )}

                    <form className="ef-panel ef-profile-form" onSubmit={envoyerDemandeProfil}>
                      <header className="ef-panel-head">
                        <h3>Demander une modification</h3>
                        <span className="ef-panel-hint">Validation requise</span>
                      </header>

                      <fieldset>
                        <legend>Contact</legend>
                        <div className="ef-form-grid">
                          <label className="ef-field">
                            <span>Email</span>
                            <input
                              type="email"
                              value={profilForm.email}
                              onChange={(e) => modifierChampProfil('email', e.target.value)}
                              placeholder="prenom.nom@ofppt.ma"
                            />
                          </label>
                          <label className="ef-field">
                            <span>Téléphone</span>
                            <input
                              type="tel"
                              maxLength={20}
                              value={profilForm.telephone}
                              onChange={(e) => modifierChampProfil('telephone', e.target.value)}
                              placeholder="06 00 00 00 00"
                            />
                          </label>
                        </div>
                      </fieldset>

                      <fieldset>
                        <legend>Statut &amp; charge</legend>
                        <div className="ef-form-grid">
                          <label className="ef-field">
                            <span>Statut</span>
                            <select
                              value={profilForm.statut}
                              onChange={(e) => modifierChampProfil('statut', e.target.value)}
                            >
                              {STATUTS_PROFIL.map((statut) => (
                                <option key={statut.id} value={statut.id}>
                                  {statut.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="ef-field">
                            <span>Heures max / semaine</span>
                            <input
                              type="number"
                              min="0"
                              max="60"
                              step="0.5"
                              value={profilForm.heures_max_semaine}
                              onChange={(e) =>
                                modifierChampProfil('heures_max_semaine', e.target.value)
                              }
                            />
                          </label>
                        </div>
                      </fieldset>

                      <fieldset>
                        <legend>Salles préférées</legend>
                        <div className="ef-form-grid ef-form-grid--3">
                          {[
                            ['salle_preferee_id', 'Salle générale'],
                            ['salle_preferee_matin_id', 'Matin (AM)'],
                            ['salle_preferee_apm_id', 'Après-midi (PM)'],
                          ].map(([cle, label]) => (
                            <label key={cle} className="ef-field">
                              <span>{label}</span>
                              <select
                                value={profilForm[cle]}
                                onChange={(e) => modifierChampProfil(cle, e.target.value)}
                              >
                                <option value="">Aucune préférence</option>
                                {salles.map((salle) => (
                                  <option key={salle.id} value={salle.id}>
                                    {salle.nom}
                                  </option>
                                ))}
                              </select>
                            </label>
                          ))}
                        </div>
                      </fieldset>

                      <label className="ef-field">
                        <span>Motif / précisions (optionnel)</span>
                        <textarea
                          rows={3}
                          maxLength={1000}
                          value={profilCommentaire}
                          onChange={(e) => setProfilCommentaire(e.target.value)}
                          placeholder="Expliquez brièvement votre demande…"
                        />
                      </label>

                      <div className="ef-form-actions">
                        <p className="ef-form-hint">
                          Les modifications seront appliquées après validation par
                          l'administration. Votre fiche actuelle reste inchangée en attendant.
                        </p>
                        <button
                          type="submit"
                          className="ef-btn ef-btn--primary"
                          disabled={savingProfil || loadingDemandes}
                        >
                          {savingProfil
                            ? 'Envoi…'
                            : demandeEnAttente
                              ? 'Mettre à jour ma demande'
                              : 'Envoyer la demande'}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>

                <section className="ef-panel ef-profile-history">
                  <header className="ef-panel-head">
                    <h3>Historique des demandes</h3>
                    <span className="ef-panel-hint">
                      {demandesProfil.filter((d) => d.statut !== 'en_attente').length} traitée
                      {demandesProfil.filter((d) => d.statut !== 'en_attente').length > 1
                        ? 's'
                        : ''}
                    </span>
                  </header>
                  {loadingDemandes ? (
                    <div className="ef-empty">Chargement de vos demandes…</div>
                  ) : demandesProfil.filter((d) => d.statut !== 'en_attente').length === 0 ? (
                    <p className="ef-muted">Aucune demande traitée pour le moment.</p>
                  ) : (
                    <div className="ef-table-wrap">
                      <table className="ef-table">
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Statut</th>
                            <th>Modifications demandées</th>
                            <th>Commentaire de l'administration</th>
                          </tr>
                        </thead>
                        <tbody>
                          {demandesProfil
                            .filter((d) => d.statut !== 'en_attente')
                            .map((demande) => (
                              <tr key={demande.id}>
                                <td>{formatDate(demande.date_demande)}</td>
                                <td>
                                  <span
                                    className={`ef-demande-badge ef-demande-badge--${demande.statut}`}
                                  >
                                    {STATUTS_DEMANDE[demande.statut] || demande.statut}
                                  </span>
                                </td>
                                <td>
                                  {changementsDemande(demande)
                                    .map((c) => `${c.label} : ${c.avant} → ${c.apres}`)
                                    .join(' · ') || '—'}
                                </td>
                                <td>{demande.commentaire_admin || '—'}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </>
            )}
          </div>
        )}
      </main>

      <footer className="espace-formateur__footer">
        OFPPT — {institute.fullName}
      </footer>
    </div>
  )
}
