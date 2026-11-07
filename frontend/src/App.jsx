import { useState, useEffect } from 'react'
import Navbar from './components/Navbar/Navbar'
import Hero from './components/Hero/Hero'
import About from './components/About/About'
import Formations from './components/Formations/Formations'
import Actualites from './components/Actualites/Actualites'
import Footer from './components/Footer/Footer'
import Login from './components/Login/Login'
import Dashboard from './components/Dashboard/Dashboard'
import EspaceFormateur from './components/EspaceFormateur/EspaceFormateur'

const ROLE_STORAGE_KEY = 'gestemploi_role'
const EMAIL_STORAGE_KEY = 'gestemploi_email'

function App() {
  const [currentView, setCurrentView] = useState(() => {
    const hash = window.location.hash
    if (hash === '#login') return 'login'
    if (hash === '#dashboard') return 'dashboard'
    return 'home'
  })
  const [userRole, setUserRole] = useState(() => {
    try {
      return window.localStorage.getItem(ROLE_STORAGE_KEY)
    } catch {
      return null
    }
  })
  const [userEmail, setUserEmail] = useState(() => {
    try {
      return window.localStorage.getItem(EMAIL_STORAGE_KEY) || ''
    } catch {
      return ''
    }
  })

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash
      if (hash === '#login') {
        setCurrentView('login')
        window.scrollTo({ top: 0, behavior: 'smooth' })
      } else if (hash === '#dashboard') {
        setCurrentView('dashboard')
        window.scrollTo({ top: 0, behavior: 'smooth' })
      } else {
        setCurrentView('home')
      }
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const navigateToLogin = () => {
    window.location.hash = '#login'
    setCurrentView('login')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const navigateToHome = () => {
    window.location.hash = '#hero'
    setCurrentView('home')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleLoginSuccess = (role, identifier = '') => {
    setUserRole(role)
    setUserEmail(identifier)
    try {
      window.localStorage.setItem(ROLE_STORAGE_KEY, role)
      window.localStorage.setItem(EMAIL_STORAGE_KEY, identifier)
    } catch {
      // Stockage indisponible : la session reste valable jusqu'au rechargement.
    }
    window.location.hash = '#dashboard'
    setCurrentView('dashboard')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleLogout = () => {
    setUserRole(null)
    setUserEmail('')
    try {
      window.localStorage.removeItem(ROLE_STORAGE_KEY)
      window.localStorage.removeItem(EMAIL_STORAGE_KEY)
    } catch {
      // Ignorer les erreurs de stockage.
    }
    navigateToHome()
  }

  if (currentView === 'login') {
    return <Login onBackHome={navigateToHome} onLoginSuccess={handleLoginSuccess} />
  }

  if (currentView === 'dashboard') {
    // Le profil formateur n'a accès à aucune fonction d'administration :
    // son interface dédiée regroupe ses disponibilités et son emploi du temps.
    if (userRole === 'formateur') {
      return <EspaceFormateur email={userEmail} onLogout={handleLogout} />
    }
    return <Dashboard role="admin" onLogout={handleLogout} />
  }

  return (
    <div className="app">
      <Navbar onNavigateToLogin={navigateToLogin} />
      <main>
        <Hero />
        <About />
        <Formations />
        <Actualites />
      </main>
      <Footer onNavigateToLogin={navigateToLogin} />
    </div>
  )
}

export default App
