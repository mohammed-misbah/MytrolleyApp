import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, LayoutGrid, Store } from 'lucide-react'
import type { Store as StoreType } from '@/types'

const ALL_VALUE = ''

type Props = {
  value: number | ''
  stores: StoreType[]
  onChange: (value: number | '') => void
}

export function StoreSelect({ value, stores, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const [typeAhead, setTypeAhead] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const nativeRef = useRef<HTMLSelectElement>(null)
  const closeTimer = useRef<number | null>(null)

  const options = [
    { value: ALL_VALUE as number | '', label: 'All stores', name: 'All stores', code: '' },
    ...stores.map((store) => ({
      value: store.id as number | '',
      label: `${store.name} (${store.code})`,
      name: store.name,
      code: store.code,
    })),
  ]
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value))

  const openPanel = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current)
    setClosing(false)
    setOpen(true)
    setHighlight(selectedIndex)
    window.setTimeout(() => {
      listRef.current
        ?.querySelectorAll('[data-testid="store-select-option"]')
        [selectedIndex]?.scrollIntoView({ block: 'nearest' })
    }, 0)
  }

  const closePanel = (restoreFocus = false) => {
    setClosing(true)
    closeTimer.current = window.setTimeout(() => {
      setOpen(false)
      setClosing(false)
      if (restoreFocus) triggerRef.current?.focus()
    }, 100)
  }

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) closePanel()
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  useEffect(() => {
    return () => {
      if (closeTimer.current !== null) window.clearTimeout(closeTimer.current)
    }
  }, [])

  const choose = (index: number) => {
    const option = options[index]
    onChange(option.value)
    if (nativeRef.current) nativeRef.current.value = String(option.value)
    closePanel(true)
  }

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      closePanel(true)
      return
    }
    if (event.key === 'Tab') {
      closePanel()
      return
    }
    if (!open && (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault()
      openPanel()
      return
    }
    if (!open) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlight((index) => (index + 1) % options.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlight((index) => (index <= 0 ? options.length - 1 : index - 1))
    } else if (event.key === 'Home') {
      event.preventDefault()
      setHighlight(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      setHighlight(options.length - 1)
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      choose(highlight)
    } else if (event.key.length === 1 && /[a-z0-9]/i.test(event.key)) {
      const term = (typeAhead + event.key).toLowerCase()
      setTypeAhead(term)
      const found = options.findIndex((option) => option.name.toLowerCase().startsWith(term))
      if (found >= 0) setHighlight(found)
      window.setTimeout(() => setTypeAhead(''), 700)
    }
  }

  const selected = options[selectedIndex]

  return (
    <div ref={rootRef} className="mt-store-select relative">
      <style>{`
        .mt-store-select-trigger {
          display: flex; align-items: center; gap: 10px;
          height: 46px; padding: 0 16px; border-radius: 14px;
          background: #FFFFFF; border: 1px solid rgba(18,45,32,.09);
          box-shadow: 0 2px 8px rgba(20,55,38,.05); cursor: pointer;
          transition: border-color 160ms, box-shadow 160ms;
        }
        .mt-store-select-trigger:hover { border-color: rgba(18,45,32,.16); }
        .mt-store-select-trigger:focus-visible,
        .mt-store-select-trigger[data-open="true"] {
          border-color: rgba(14,61,40,.45);
          box-shadow: 0 0 0 3px rgba(14,61,40,.12);
          outline: none;
        }
        .mt-store-select-chevron { transition: transform 160ms; }
        .mt-store-select-chevron[data-open="true"] { transform: rotate(180deg); }
        .mt-store-select-panel {
          position: absolute; right: 0; margin-top: 8px; z-index: 50;
          width: max(100%, 300px); max-height: 320px; overflow-y: auto;
          background: #FFFFFF; border: 1px solid rgba(18,45,32,.08);
          border-radius: 16px; padding: 8px;
          box-shadow: 0 18px 40px rgba(20,55,38,.14), 0 2px 6px rgba(20,55,38,.06);
          animation: mt-store-in 140ms ease-out both;
        }
        .mt-store-select-panel[data-closing="true"] { animation: mt-store-out 100ms ease-in both; }
        @keyframes mt-store-in {
          from { opacity: 0; transform: translateY(-6px) scale(.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes mt-store-out {
          from { opacity: 1; transform: translateY(0) scale(1); }
          to { opacity: 0; transform: translateY(-6px) scale(.98); }
        }
        .mt-store-select-panel::-webkit-scrollbar { width: 6px; }
        .mt-store-select-panel::-webkit-scrollbar-thumb { background: rgba(18,45,32,.18); border-radius: 6px; }
        .mt-store-select-panel::-webkit-scrollbar-track { background: transparent; }
        .mt-store-select-option {
          display: flex; align-items: center; gap: 12px;
          height: 44px; padding: 0 12px; border-radius: 10px;
          font-size: 14px; font-weight: 500; color: #13241B;
          width: 100%; border: none; background: transparent; cursor: pointer;
          text-align: left; transition: background-color 120ms;
        }
        .mt-store-select-option:hover, .mt-store-select-option[data-highlight="true"] { background: #F3F6F4; }
        .mt-store-select-option[data-selected="true"] {
          background: linear-gradient(145deg,#14402B,#0C241A); color: #FFFFFF;
        }
        .mt-store-select-chip {
          display: flex; align-items: center; justify-content: center;
          width: 28px; height: 28px; border-radius: 8px;
          background: #E9EFEB; color: #14704F; flex-shrink: 0;
        }
        .mt-store-select-option[data-selected="true"] .mt-store-select-chip {
          background: rgba(255,255,255,.14); color: #FFFFFF;
        }
        .mt-store-select-badge {
          margin-left: auto; font-size: 11.5px; font-weight: 600;
          color: #5E6E65; background: #F2F5F3; padding: 2px 7px; border-radius: 6px;
        }
        .mt-store-select-option[data-selected="true"] .mt-store-select-badge {
          background: rgba(255,255,255,.18); color: #FFFFFF;
        }
        .mt-store-native {
          position: absolute; opacity: 0; pointer-events: none;
          width: 1px; height: 1px; padding: 0; margin: 0; border: 0;
        }
        .mt-store-divider { height: 1px; background: rgba(18,45,32,.07); margin: 6px 4px; }
        @media (max-width: 639px) {
          .mt-store-select-trigger { width: 100%; }
          .mt-store-select-panel { width: 100%; max-height: 280px; }
        }
      `}</style>

      <select
        ref={nativeRef}
        value={value}
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : '')}
        className="mt-store-native"
        tabIndex={-1}
        aria-hidden
      >
        <option value="">All stores</option>
        {stores.map((store) => (
          <option key={store.id} value={store.id}>{store.name} ({store.code})</option>
        ))}
      </select>

      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="mt-store-select-panel"
        data-testid="store-select-trigger"
        data-open={open}
        className="mt-store-select-trigger"
        onClick={() => (open ? closePanel() : openPanel())}
        onKeyDown={onKeyDown}
      >
        <span style={{ fontSize: 13.5, color: '#5E6E65' }}>Select store</span>
        <span style={{ fontSize: 13.5, fontWeight: 500, color: '#13241B' }}>{selected.name}</span>
        <ChevronDown
          className="mt-store-select-chevron"
          data-open={open}
          size={16}
          strokeWidth={1.8}
          style={{ color: '#5E6E65', marginLeft: 'auto' }}
          aria-hidden
        />
      </button>

      {open && (
        <div
          id="mt-store-select-panel"
          ref={listRef}
          role="listbox"
          data-closing={closing}
          className="mt-store-select-panel"
          onKeyDown={onKeyDown}
        >
          {options.map((option, index) => (
            <div key={option.value}>
              {index === 1 && <div className="mt-store-divider" />}
              <button
                type="button"
                role="option"
                aria-selected={option.value === value}
                aria-label={option.label}
                data-testid="store-select-option"
                data-selected={option.value === value}
                data-highlight={index === highlight}
                className="mt-store-select-option"
                onClick={() => choose(index)}
                onMouseEnter={() => setHighlight(index)}
              >
                <span className="mt-store-select-chip">
                  {index === 0 ? (
                    <LayoutGrid size={16} strokeWidth={1.8} />
                  ) : (
                    <Store size={16} strokeWidth={1.8} />
                  )}
                </span>
                <span>{option.name}</span>
                {option.code && <span className="mt-store-select-badge">{option.code}</span>}
                {option.value === value && <Check size={16} strokeWidth={1.8} aria-hidden />}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
