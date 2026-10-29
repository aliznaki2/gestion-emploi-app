import { useState } from 'react'
import './Login.css'

export default function Login({ onBackHome, onLoginSuccess }) {
  const [role, setRole] = useState('admin') // 'admin' | 'formateur'
  const [identifier, setIdentifier] = useState('admin@ofppt-ntic.ma')
  const [password, setPassword] = useState('••••••••••')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [authSuccess, setAuthSuccess] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  const handleRoleChange = (newRole) => {
    setRole(newRole)
    setErrorMsg('')
    setAuthSuccess(false)
    if (newRole === 'admin') {
      setIdentifier('admin@ofppt-ntic.ma')
      setPassword('Admin2026*')
    } else {
      setIdentifier('formateur.alami@ofppt.ma')
      setPassword('Formateur2026*')
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!identifier || !password) {
      setErrorMsg('Veuillez remplir tous les champs obligatoires.')
      return
    }

    setErrorMsg('')
    setIsLoading(true)

    // Simulate authenticating
    setTimeout(() => {
      setIsLoading(false)
      setAuthSuccess(true)
      // Navigate to dashboard after short success display
      setTimeout(() => {
        if (onLoginSuccess) onLoginSuccess(role)
      }, 800)
    }, 900)
  }

  return (
    <div className="login-page" id="login-page">
      
      {/* ── Top Bar ── */}
      <header className="login-page__topbar">
        <div className="container login-page__topbar-inner">
          <button
            type="button"
            className="login-page__back-btn"
            onClick={onBackHome}
            id="btn-back-home"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Retour à l'accueil
          </button>

          <div className="login-page__brand">
            <img src="/ofppt.png" alt="OFPPT" className="login-page__ofppt-logo" />
            <div className="login-page__brand-text">
              <span className="login-page__brand-name">ISTA NTIC 2</span>
              <span className="login-page__brand-sub">Sidi Maârouf · Casablanca</span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Main Container ── */}
      <div className="login-page__main container">
        <div className="login-card">
          {/* Login Form */}
          <div className="login-card__form-area">
            
            <div className="login-card__header">
              <span className="login-card__pretitle">Portail d'authentification</span>
              <h1 className="login-card__title">Connexion à votre compte</h1>
              <p className="login-card__subtitle">
                Sélectionnez votre profil pour accéder à votre espace de travail.
              </p>
            </div>

            {/* Profile Tabs (Administration and Formateur only) */}
            <div className="login-role-tabs" role="tablist" aria-label="Profil de connexion">
              <button
                type="button"
                className={`login-role-tab ${role === 'admin' ? 'active' : ''}`}
                onClick={() => handleRoleChange('admin')}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2a5 5 0 0 1 5 5v2a5 5 0 0 1-10 0V7a5 5 0 0 1 5-5z" />
                  <path d="M19 21v-2a7 7 0 0 0-14 0v2" />
                </svg>
                Administration
              </button>
              <button
                type="button"
                className={`login-role-tab ${role === 'formateur' ? 'active' : ''}`}
                onClick={() => handleRoleChange('formateur')}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                </svg>
                Formateur
              </button>
            </div>

            {/* Error Message */}
            {errorMsg && (
              <div className="login-alert login-alert--error" role="alert">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Success Message */}
            {authSuccess ? (
              <div className="login-success-box">
                <div className="login-success-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <h3>Connexion réussie !</h3>
                <p>
                  Bienvenue sur votre espace <strong>{role === 'admin' ? 'Administrateur' : 'Formateur'}</strong> ISTA NTIC 2.
                </p>
                <div className="login-success-info">
                  <span>Identifiant : {identifier}</span>
                  <span>Établissement : ISTA NTIC 2 Sidi Maârouf</span>
                </div>
                <button
                  type="button"
                  className="login-success-btn"
                  onClick={() => onLoginSuccess ? onLoginSuccess(role) : onBackHome()}
                >
                  Accéder au tableau de bord →
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="login-form">
                
                {/* Identifier Input */}
                <div className="form-group">
                  <label htmlFor="user-id" className="form-label">
                    {role === 'admin'
                      ? 'Adresse e-mail administrateur'
                      : 'Adresse e-mail formateur'}
                  </label>
                  <div className="input-wrap">
                    <span className="input-icon" aria-hidden="true">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                        <polyline points="22,6 12,13 2,6" />
                      </svg>
                    </span>
                    <input
                      id="user-id"
                      type="email"
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      placeholder={
                        role === 'admin'
                          ? 'ex: admin@ofppt-ntic.ma'
                          : 'ex: nom.prenom@ofppt.ma'
                      }
                      className="form-input"
                      required
                    />
                  </div>
                </div>

                {/* Password Input */}
                <div className="form-group">
                  <div className="form-label-row">
                    <label htmlFor="user-pwd" className="form-label">
                      Mot de passe
                    </label>
                    <a
                      href="#forgot"
                      className="form-forgot-link"
                      onClick={(e) => {
                        e.preventDefault()
                        alert('Pour réinitialiser votre mot de passe, veuillez contacter le secrétariat ISTA NTIC 2 à istanticsm@gmail.com')
                      }}
                    >
                      Mot de passe oublié ?
                    </a>
                  </div>
                  <div className="input-wrap">
                    <span className="input-icon" aria-hidden="true">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                    </span>
                    <input
                      id="user-pwd"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Entrez votre mot de passe"
                      className="form-input form-input--has-toggle"
                      required
                    />
                    <button
                      type="button"
                      className="input-toggle-pwd"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                    >
                      {showPassword ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                          <line x1="1" y1="1" x2="23" y2="23" />
                        </svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                {/* Remember Me */}
                <div className="form-remember">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      className="checkbox-input"
                    />
                    <span>Mémoriser ma session sur cet appareil</span>
                  </label>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  className="login-submit-btn"
                  disabled={isLoading}
                  id="btn-submit-login"
                >
                  {isLoading ? (
                    <>
                      <span className="login-spinner" aria-hidden="true"></span>
                      Vérification en cours...
                    </>
                  ) : (
                    <>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                        <polyline points="10 17 15 12 10 7" />
                        <line x1="15" y1="12" x2="3" y2="12" />
                      </svg>
                      Se connecter en tant que {role === 'admin' ? 'Administrateur' : 'Formateur'}
                    </>
                  )}
                </button>

                {/* Demo Helper Box */}
                <div className="login-demo-helper">
                  <span className="demo-helper-title">Comptes de démonstration pré-configurés :</span>
                  <div className="demo-helper-btns">
                    <button
                      type="button"
                      className={`demo-pill ${role === 'admin' ? 'demo-pill--active' : ''}`}
                      onClick={() => handleRoleChange('admin')}
                    >
                      Admin
                    </button>
                    <button
                      type="button"
                      className={`demo-pill ${role === 'formateur' ? 'demo-pill--active' : ''}`}
                      onClick={() => handleRoleChange('formateur')}
                    >
                      Formateur
                    </button>
                  </div>
                </div>

                {/* Help support */}
                <div className="login-support">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="16" x2="12" y2="12" />
                    <line x1="12" y1="8" x2="12.01" y2="8" />
                  </svg>
                  <span>
                    Problème d'accès ? Contactez le support :&nbsp;
                    <a href="mailto:istanticsm@gmail.com">istanticsm@gmail.com</a>
                  </span>
                </div>

              </form>
            )}

          </div>

        </div>
      </div>

    </div>
  )
}
