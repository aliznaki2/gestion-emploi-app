import { useEffect, useRef, useState } from 'react'
import { NETWORK_NAME } from '../../config/branding'
import './SubscriptionModal.css'

const EMPTY_FORM = {
  institute: '',
  city: '',
  contact: '',
  role: '',
  email: '',
  phone: '',
  message: '',
}

const CHECK_ICON = (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

const CLOSE_ICON = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
)

export default function SubscriptionModal({ onClose }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [status, setStatus] = useState('idle')
  const firstFieldRef = useRef(null)
  const timerRef = useRef(null)

  /* Échap pour fermer + blocage du défilement de la page. */
  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)

    const focusTimer = window.setTimeout(() => firstFieldRef.current?.focus(), 80)

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKey)
      window.clearTimeout(focusTimer)
    }
  }, [onClose])

  /* Nettoyage du minuteur de confirmation. */
  useEffect(() => () => window.clearTimeout(timerRef.current), [])

  const update = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }))
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (status === 'sending') return
    setStatus('sending')
    timerRef.current = window.setTimeout(() => setStatus('sent'), 650)
  }

  const handleOverlay = (event) => {
    if (event.target === event.currentTarget) onClose()
  }

  return (
    <div className="subscription-modal" role="presentation" onMouseDown={handleOverlay}>
      <div
        className="subscription-modal__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="subscription-title"
      >
        <button
          type="button"
          className="subscription-modal__close"
          onClick={onClose}
          aria-label="Fermer la fenêtre d'abonnement"
        >
          {CLOSE_ICON}
        </button>

        {status === 'sent' ? (
          <div className="subscription-modal__success">
            <span className="subscription-modal__success-icon" aria-hidden="true">
              {CHECK_ICON}
            </span>
            <h2 className="subscription-modal__success-title" id="subscription-title">
              Demande envoyée
            </h2>
            <p className="subscription-modal__success-text">
              Merci&nbsp;! Votre demande d'abonnement au <strong>{NETWORK_NAME}</strong> a bien
              été enregistrée. L'équipe GestEmploi vous contactera pour mettre en place
              l'espace de travail{form.institute ? ` de ${form.institute}` : ' de votre institut'}.
            </p>
            <div className="subscription-modal__success-meta">
              <span>Délai de réponse estimé&nbsp;: 48 h ouvrées</span>
              <span>{form.email || 'contact fourni dans la demande'}</span>
            </div>
            <div className="subscription-modal__success-actions">
              <button type="button" className="subscription-modal__btn subscription-modal__btn--primary" onClick={onClose}>
                Terminer
              </button>
              <button
                type="button"
                className="subscription-modal__btn subscription-modal__btn--ghost"
                onClick={() => {
                  setForm(EMPTY_FORM)
                  setStatus('idle')
                }}
              >
                Nouvelle demande
              </button>
            </div>
          </div>
        ) : (
          <>
            <header className="subscription-modal__head">
              <span className="subscription-modal__eyebrow">Abonnement institut</span>
              <h2 className="subscription-modal__title" id="subscription-title">
                Rejoindre le réseau GestEmploi
              </h2>
              <p className="subscription-modal__subtitle">
                Votre ISTA n'apparaît pas encore dans le réseau&nbsp;? Remplissez ce formulaire
                et nous préparerons votre espace de travail.
              </p>
            </header>

            <form className="subscription-modal__form" onSubmit={handleSubmit}>
              <div className="subscription-modal__grid">
                <label className="subscription-modal__field subscription-modal__field--wide">
                  <span className="subscription-modal__label">Nom de l'institut *</span>
                  <input
                    ref={firstFieldRef}
                    type="text"
                    value={form.institute}
                    onChange={update('institute')}
                    placeholder="Ex. ISTA NTIC 2"
                    required
                    autoComplete="organization"
                  />
                </label>

                <label className="subscription-modal__field">
                  <span className="subscription-modal__label">Ville *</span>
                  <input
                    type="text"
                    value={form.city}
                    onChange={update('city')}
                    placeholder="Casablanca"
                    required
                    autoComplete="address-level2"
                  />
                </label>

                <label className="subscription-modal__field">
                  <span className="subscription-modal__label">Fonction</span>
                  <input
                    type="text"
                    value={form.role}
                    onChange={update('role')}
                    placeholder="Directeur, responsable pédagogique…"
                  />
                </label>

                <label className="subscription-modal__field">
                  <span className="subscription-modal__label">Personne de contact *</span>
                  <input
                    type="text"
                    value={form.contact}
                    onChange={update('contact')}
                    placeholder="Nom et prénom"
                    required
                    autoComplete="name"
                  />
                </label>

                <label className="subscription-modal__field">
                  <span className="subscription-modal__label">E-mail *</span>
                  <input
                    type="email"
                    value={form.email}
                    onChange={update('email')}
                    placeholder="contact@institut.ma"
                    required
                    autoComplete="email"
                  />
                </label>

                <label className="subscription-modal__field">
                  <span className="subscription-modal__label">Téléphone</span>
                  <input
                    type="tel"
                    value={form.phone}
                    onChange={update('phone')}
                    placeholder="+212 5 22 00 00 00"
                    autoComplete="tel"
                  />
                </label>

                <label className="subscription-modal__field subscription-modal__field--wide">
                  <span className="subscription-modal__label">Votre besoin</span>
                  <textarea
                    rows="3"
                    value={form.message}
                    onChange={update('message')}
                    placeholder="Nombre de groupes, sections, formateurs, échéances…"
                  />
                </label>
              </div>

              <p className="subscription-modal__hint">
                Les champs marqués d'un * sont obligatoires. Aucun engagement n'est demandé à cette étape.
              </p>

              <div className="subscription-modal__actions">
                <button
                  type="button"
                  className="subscription-modal__btn subscription-modal__btn--ghost"
                  onClick={onClose}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="subscription-modal__btn subscription-modal__btn--primary"
                  disabled={status === 'sending'}
                >
                  {status === 'sending' ? 'Envoi en cours…' : "Envoyer la demande"}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
