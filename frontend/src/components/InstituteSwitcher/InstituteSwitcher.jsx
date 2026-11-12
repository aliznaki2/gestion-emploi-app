import { useEffect, useId, useRef, useState } from 'react'
import { INSTITUTES, useInstitute } from '../../config/branding'
import './InstituteSwitcher.css'

const CHECK_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

const CHEVRON_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="6 9 12 15 18 9" />
  </svg>
)

const BUILDING_ICON = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 21h18" />
    <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
    <path d="M9 7h1M14 7h1M9 11h1M14 11h1M9 15h1M14 15h1" />
  </svg>
)

const PLUS_ICON = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
)

export default function InstituteSwitcher({
  variant = 'light',
  compact = false,
  align = 'left',
  className = '',
  onSubscribe,
}) {
  const [institute, changeInstitute] = useInstitute()
  const [open, setOpen] = useState(false)
  const [placement, setPlacement] = useState('down')
  const [menuMaxHeight, setMenuMaxHeight] = useState(null)
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const listId = useId()

  useEffect(() => {
    if (!open) return undefined

    const handlePointer = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    const handleKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', handlePointer)
    document.addEventListener('touchstart', handlePointer)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handlePointer)
      document.removeEventListener('touchstart', handlePointer)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  const toggle = () => {
    const next = !open
    if (next) {
      const rect = triggerRef.current?.getBoundingClientRect()
      if (rect) {
        const spaceBelow = window.innerHeight - rect.bottom - 16
        const spaceAbove = rect.top - 16
        const openUp = spaceBelow < 340 && spaceAbove > spaceBelow
        const available = openUp ? spaceAbove : spaceBelow
        setPlacement(openUp ? 'up' : 'down')
        setMenuMaxHeight(Math.max(180, Math.min(460, available)))
      }
    }
    setOpen(next)
  }

  const select = (id) => {
    changeInstitute(id)
    setOpen(false)
  }

  const handleSubscribe = () => {
    setOpen(false)
    if (onSubscribe) onSubscribe()
  }

  return (
    <div
      className={`institute-switcher institute-switcher--${variant}${compact ? ' institute-switcher--compact' : ''} ${className}`.trim()}
      ref={rootRef}
    >
      <button
        type="button"
        ref={triggerRef}
        className="institute-switcher__trigger"
        onClick={toggle}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        title="Changer d'institut"
      >
        <span className="institute-switcher__mark" aria-hidden="true">
          {institute.code}
        </span>
        <span className="institute-switcher__identity">
          <span className="institute-switcher__name">{institute.name}</span>
          <span className="institute-switcher__meta">
            {institute.district} · {institute.city}
          </span>
        </span>
        <span className={`institute-switcher__chevron${open ? ' is-open' : ''}`} aria-hidden="true">
          {CHEVRON_ICON}
        </span>
      </button>

      {open && (
        <div
          className={`institute-switcher__menu institute-switcher__menu--${align} institute-switcher__menu--${placement}`}
          id={listId}
          role="listbox"
          aria-label="Sélection de l'institut"
          style={menuMaxHeight ? { maxHeight: `${menuMaxHeight}px` } : undefined}
        >
          <div className="institute-switcher__menu-head">
            <span className="institute-switcher__menu-icon" aria-hidden="true">
              {BUILDING_ICON}
            </span>
            <div>
              <p className="institute-switcher__menu-title">Espace de travail</p>
            </div>
          </div>

          <div className="institute-switcher__options">
            {INSTITUTES.map((item) => {
              const selected = item.id === institute.id
              return (
                <button
                  key={item.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`institute-switcher__option${selected ? ' is-selected' : ''}`}
                  onClick={() => select(item.id)}
                >
                  <span
                    className="institute-switcher__option-mark"
                    style={{ '--institute-accent': item.accent }}
                    aria-hidden="true"
                  >
                    {item.code}
                  </span>
                  <span className="institute-switcher__option-text">
                    <span className="institute-switcher__option-name">{item.name}</span>
                    <span className="institute-switcher__option-meta">
                      {item.district} · {item.city}
                    </span>
                  </span>
                  {selected && (
                    <span className="institute-switcher__option-check" aria-hidden="true">
                      {CHECK_ICON}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {onSubscribe && (
            <div className="institute-switcher__empty">
              <span className="institute-switcher__empty-icon" aria-hidden="true">
                {PLUS_ICON}
              </span>
              <div className="institute-switcher__empty-text">
                <p className="institute-switcher__empty-title">Votre institut n'est pas encore listé ?</p>
                <p className="institute-switcher__empty-desc">
                  Les autres ISTA rejoindront le réseau au fil des abonnements.
                </p>
              </div>
              <button
                type="button"
                className="institute-switcher__subscribe"
                onClick={handleSubscribe}
              >
                S'abonner
              </button>
            </div>
          )}

          <p className="institute-switcher__foot">
            {INSTITUTES.length > 1
              ? "L'institut sélectionné devient votre espace de travail."
              : "Cet institut est le premier espace de travail du réseau."}
          </p>
        </div>
      )}
    </div>
  )
}
