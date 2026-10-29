import { useState, useEffect } from 'react'
import Navbar from './components/Navbar/Navbar'
import Hero from './components/Hero/Hero'
import About from './components/About/About'
import Formations from './components/Formations/Formations'
import Actualites from './components/Actualites/Actualites'
import Footer from './components/Footer/Footer'
import Login from './components/Login/Login'
import Dashboard from './components/Dashboard/Dashboard'

function App() {
  const [currentView, setCurrentView] = useState(() => {
    const hash = window.location.hash
    if (hash === '#login') return 'login'
    if (hash === '#dashboard') return 'dashboard'
    return 'home'
  })
  const [userRole, setUserRole] = useState(null)

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

  const handleLoginSuccess = (role) => {
    setUserRole(role)
    window.location.hash = '#dashboard'
    setCurrentView('dashboard')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleLogout = () => {
    setUserRole(null)
    navigateToHome()
  }

  if (currentView === 'login') {
    return <Login onBackHome={navigateToHome} onLoginSuccess={handleLoginSuccess} />
  }

  if (currentView === 'dashboard') {
    return <Dashboard role={userRole || 'admin'} onLogout={handleLogout} />
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
