import { useEffect, useState, type ReactNode } from 'react';
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useSession } from '../session';
import { ThemeToggle } from './Appearance';
import { PortalBrand } from './PublicLayout';
import { ROLE_LABELS } from '../lib/labels';
import { APP_NAME } from '../lib/branding';

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  visible: boolean;
}

const ROUTE_TITLES: [string, string][] = [
  ['/compras', 'Compras'],
  ['/proveedores', 'Proveedores'],
  ['/evaluar', 'Comparar ofertas'],
  ['/reglas', 'Normativa y flujo'],
  ['/auditoria', 'Auditoría'],
  ['/administracion', 'Administración'],
  ['/preferencias', 'Preferencias'],
];

function crumbFor(pathname: string): string {
  if (pathname === '/gestion') return 'Mi escritorio';
  const match = ROUTE_TITLES.find(([prefix]) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  return match?.[1] ?? 'Escritorio';
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'CP';
  return parts.slice(0, 2).map((p) => p[0]!.toUpperCase()).join('');
}

export function Layout() {
  const { user, can, logout } = useSession();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  const items: NavItem[] = [
    { to: '/gestion', label: 'Mi escritorio', end: true, visible: can('dashboard.read') },
    { to: '/evaluar', label: 'Comparar ofertas', visible: can('offer.read') },
    { to: '/compras', label: 'Compras', visible: can('case.read') },
    { to: '/proveedores', label: 'Proveedores', visible: can('supplier.manage') },
  ];
  const control: NavItem[] = [
    { to: '/auditoria', label: 'Auditoría', visible: can('audit.read') },
    { to: '/reglas', label: 'Normativa y flujo', visible: true },
    { to: '/administracion', label: 'Administración', visible: can('admin.users') || can('admin.areas') || can('admin.rules') },
    { to: '/preferencias', label: 'Preferencias', visible: true },
  ];

  const renderNav = (list: NavItem[]) =>
    list
      .filter((item) => item.visible)
      .map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end}>
          {item.label}
        </NavLink>
      ));

  return (
    <>
      <aside className={`sidebar ${drawerOpen ? 'open' : ''}`} id="sidebar" aria-label="Navegación principal">
        <PortalBrand />
        <nav>
          <div className="nav">{renderNav(items)}</div>
          <details className="nav-tools" open={control.some((item) => item.visible && location.pathname === item.to)}>
            <summary>Más herramientas</summary>
            <div className="nav">{renderNav(control)}</div>
          </details>
        </nav>
        <div className="sidebar-foot">
          <Link to="/">Volver al portal público</Link>
          <p>Sesión de {ROLE_LABELS[user.roles[0] ?? ''] ?? 'usuario'} · {user.area ?? 'Sin área asignada'}</p>
        </div>
      </aside>
      <div className={`drawer-backdrop ${drawerOpen ? 'open' : ''}`} onClick={() => setDrawerOpen(false)} aria-hidden="true" />
      <div className="workspace">
        <header className="topbar">
          <div className="row">
            <button
              type="button"
              className="btn secondary menu-btn"
              aria-label="Abrir navegación"
              aria-expanded={drawerOpen}
              aria-controls="sidebar"
              onClick={() => setDrawerOpen((v) => !v)}
            >
              ☰
            </button>
            <div className="crumb">{APP_NAME} › <strong>{crumbFor(location.pathname)}</strong></div>
          </div>
          <div className="user-chip">
            <ThemeToggle />
            <span className="avatar" aria-hidden="true">{initials(user.full_name)}</span>
            <span className="name">{user.full_name}</span>
            {!user.is_local_test_user && (
              <button type="button" className="btn secondary small" onClick={() => void logout()}>
                Cerrar sesión
              </button>
            )}
          </div>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="footer">
          <span>{APP_NAME}</span>
        </footer>
      </div>
    </>
  );
}

export function RequirePermission({ permission, anyOf, children }: { permission?: string; anyOf?: string[]; children: ReactNode }) {
  const { can } = useSession();
  const allowed = anyOf ? anyOf.some((p) => can(p)) : permission ? can(permission) : true;
  if (!allowed) {
    return (
      <div className="empty">
        <strong>Tu rol no tiene acceso a esta sección.</strong>
        <div>Si lo necesitás, pedilo a un administrador.</div>
      </div>
    );
  }
  return <>{children}</>;
}

export function ToLogin() {
  return <Navigate to="/login" replace />;
}
