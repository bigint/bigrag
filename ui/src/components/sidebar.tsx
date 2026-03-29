'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

const nav = [
  { href: '/', label: 'Dashboard', icon: DashboardIcon },
  { href: '/vault', label: 'Vault', icon: VaultIcon },
  { href: '/namespaces', label: 'Namespaces', icon: NamespaceIcon },
  { href: '/metrics', label: 'Metrics', icon: MetricsIcon },
  { href: '/settings', label: 'Settings', icon: SettingsIcon },
] as const

export const Sidebar = () => {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-56 flex-col border-r border-border bg-bg">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border px-5">
        <div className="flex size-7 items-center justify-center rounded-lg bg-accent">
          <span className="text-xs font-bold text-white">B</span>
        </div>
        <span className="text-sm font-semibold tracking-tight">bigRAG</span>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {nav.map(({ href, label, icon: Icon }) => {
          const isActive =
            href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors',
                isActive
                  ? 'bg-bg-hover text-text'
                  : 'text-text-muted hover:bg-bg-hover hover:text-text'
              )}
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="border-t border-border px-4 py-3 text-[11px] text-text-dim">
        v0.1.0
      </div>
    </aside>
  )
}

function DashboardIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1.5" y="1.5" width="5" height="5" rx="1" />
      <rect x="9.5" y="1.5" width="5" height="5" rx="1" />
      <rect x="1.5" y="9.5" width="5" height="5" rx="1" />
      <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
    </svg>
  )
}

function NamespaceIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4h12M2 8h12M2 12h12" />
    </svg>
  )
}

function MetricsIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 14V8l4-3 4 5 4-8" />
    </svg>
  )
}

function VaultIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="12" height="11" rx="1.5" />
      <path d="M5.5 3V1.5M10.5 3V1.5M8 7v3M6.5 8.5h3" />
    </svg>
  )
}

function SettingsIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.1 3.1l1.4 1.4M11.5 11.5l1.4 1.4M3.1 12.9l1.4-1.4M11.5 4.5l1.4-1.4" />
    </svg>
  )
}
