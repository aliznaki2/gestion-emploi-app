import { useEffect, useState } from 'react'

/* ============================================================================
   Source unique de vérité pour la marque et le réseau d'instituts.
   ----------------------------------------------------------------------------
   L'institut courant est un « espace de travail » : il est persisté dans le
   navigateur et partagé entre la page publique, le login et le dashboard via
   un évènement personnalisé.
   ========================================================================== */

export const APP_NAME = 'GestEmploi'
export const APP_TAGLINE =
  "La plateforme de gestion des emplois du temps du réseau ISTA"
export const APP_DESCRIPTION =
  "Planifiez, générez et validez les emplois du temps de votre institut en quelques minutes, sans conflit de salle ni de formateur."

export const NETWORK_NAME = 'Réseau ISTA'
export const AUTHORITY = {
  short: 'OFPPT',
  name: 'Office de la Formation Professionnelle et de la Promotion du Travail',
}

/**
 * Instituts disponibles dans l'espace de travail.
 * Seul l'institut réellement déployé est listé : les autres emplacements du
 * réseau restent volontairement vides et seront ajoutés au fil des abonnements.
 * `groupPrefix` reste aligné sur les codes groupes déjà stockés en base
 * (ex. NTIC2-FS201) afin de ne pas casser les données existantes.
 */
export const INSTITUTES = [
  {
    id: 'ntic2',
    code: 'NTIC2',
    name: 'ISTA NTIC 2',
    shortName: 'NTIC 2',
    fullName: 'Institut Spécialisé de Technologie Appliquée NTIC 2',
    city: 'Casablanca',
    district: 'Sidi Maârouf',
    address: '1029, Route de Bouskoura, Sidi Maârouf, Casablanca',
    groupPrefix: 'NTIC2',
    email: 'istanticsm@gmail.com',
    website: 'https://sites.google.com/view/ista-ntic-sm/accueil',
    accent: '#1a5fa8',
  },
]

export const DEFAULT_INSTITUTE_ID = 'ntic2'

const STORAGE_KEY = 'gestemploi_institute'
const CHANGE_EVENT = 'gestemploi:institute-change'

export function getInstitute(id) {
  return (
    INSTITUTES.find((institute) => institute.id === id) ||
    INSTITUTES.find((institute) => institute.id === DEFAULT_INSTITUTE_ID) ||
    INSTITUTES[0]
  )
}

export function readInstituteId() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_INSTITUTE_ID
  } catch {
    return DEFAULT_INSTITUTE_ID
  }
}

export function getCurrentInstitute() {
  return getInstitute(readInstituteId())
}

export function setInstitute(id) {
  const institute = getInstitute(id)
  try {
    window.localStorage.setItem(STORAGE_KEY, institute.id)
  } catch {
    // Stockage indisponible : la sélection reste valable pour la session.
  }
  window.dispatchEvent(
    new CustomEvent(CHANGE_EVENT, { detail: institute.id }),
  )
  return institute
}

/** Sélecteur d'institut réactif, partagé par tous les écrans. */
export function useInstitute() {
  const [institute, setInstituteState] = useState(getCurrentInstitute)

  useEffect(() => {
    const sync = () => setInstituteState(getCurrentInstitute())
    const onStorage = (event) => {
      if (!event.key || event.key === STORAGE_KEY) sync()
    }
    window.addEventListener(CHANGE_EVENT, sync)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  return [institute, setInstitute]
}

/** Libellé court prêt à afficher : « ISTA NTIC 2 · Casablanca ». */
export function instituteLabel(institute) {
  if (!institute) return ''
  return `${institute.name} · ${institute.city}`
}
