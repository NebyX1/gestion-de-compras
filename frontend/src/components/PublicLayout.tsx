import { useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { Person20Regular } from '@fluentui/react-icons';
import { APP_NAME } from '../lib/branding';
import { ThemeToggle } from './Appearance';

export function PortalBrand() {
  return <Link to="/" className="portal-brand" aria-label={`${APP_NAME}, inicio`}>
    <img className="portal-brand-logo" src="/images/logo-lavalleja.webp" width="559" height="720" alt="Escudo de la Intendencia de Lavalleja" />
    <span><strong>{APP_NAME}</strong><small>Intendencia de Lavalleja</small></span>
  </Link>;
}

export function PublicLayout() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash === '#licitaciones') document.getElementById('licitaciones')?.scrollIntoView();
    else {
      window.scrollTo(0, 0);
      document.getElementById('main')?.focus({ preventScroll: true });
    }
  }, [pathname, hash]);
  return <div className="public-layout">
    <header className="portal-header">
      <div className="portal-header-inner">
        <PortalBrand />
        <nav className="portal-nav" aria-label="Portal público">
          <NavLink end to="/">Licitaciones</NavLink>
          <NavLink to="/resultados">Resultados</NavLink>
        </nav>
        <div className="portal-tools">
          <ThemeToggle />
          <Link to="/gestion" className="portal-staff-link"><Person20Regular /><span>Acceso interno</span></Link>
        </div>
      </div>
    </header>
    <main id="main" className="portal-main" tabIndex={-1}><Outlet /></main>
    <footer className="portal-footer">
      <div><PortalBrand /><nav aria-label="Enlaces del pie"><Link to="/#licitaciones">Ver licitaciones</Link><Link to="/resultados">Adjudicaciones</Link></nav></div>
    </footer>
  </div>;
}
