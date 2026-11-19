import { Button, Input, Select } from '@fluentui/react-components';
import { ArrowDownRegular, ArrowLeftRegular, ArrowRightRegular, ChevronLeftRegular, ChevronRightRegular, FilterRegular, GavelRegular, SearchRegular } from '@fluentui/react-icons';
import { useEffect, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { APP_NAME } from '../lib/branding';
import { useTenders, type PublicStatus } from './api';
import { EmptyList, QueryNotice, TenderCard, usePageTitle } from './shared';

function TenderList({ results = false }: { results?: boolean }) {
  const [params, setParams] = useSearchParams();
  const search = params.get('q') || '';
  const rawStatus = params.get('estado');
  const status: PublicStatus | '' = results ? 'awarded' : rawStatus === 'open' || rawStatus === 'closed' || rawStatus === 'awarded' ? rawStatus : '';
  const page = Math.max(1, Number.parseInt(params.get('pagina') || '1', 10) || 1);
  const [draft, setDraft] = useState(search);
  const query = useTenders(search, status, page);
  const filtered = Boolean(search || (!results && status));
  const totalPages = query.data ? Math.max(1, Math.ceil(query.data.total / query.data.per_page)) : 1;
  const { hash } = useLocation();

  useEffect(() => { setDraft(search); }, [search]);
  useEffect(() => {
    if (hash === '#licitaciones') document.getElementById('licitaciones')?.scrollIntoView({ block: 'start' });
  }, [hash]);

  function apply(nextSearch: string, nextStatus: PublicStatus | '', nextPage = 1) {
    const next = new URLSearchParams();
    if (nextSearch.trim()) next.set('q', nextSearch.trim());
    if (nextStatus && !results) next.set('estado', nextStatus);
    if (nextPage > 1) next.set('pagina', String(nextPage));
    setParams(next, { preventScrollReset: true });
  }

  return <section className="pu-section" id={results ? 'adjudicaciones' : 'licitaciones'} aria-labelledby="pu-list-title">
    <div className="pu-section-heading"><div>
      <h2 id="pu-list-title">{results ? 'Adjudicaciones publicadas' : 'Licitaciones publicadas'}</h2>
      <p>{results ? 'Buscá la compra para consultar la oferta ganadora y los fundamentos de la decisión.' : 'Consultá los llamados, sus requisitos y las fechas de cierre.'}</p>
    </div>
      {query.data && <span className="pu-count">{query.data.total} {query.data.total === 1 ? 'resultado' : 'resultados'}</span>}
    </div>
    <form className="pu-filters" role="search" onSubmit={event => { event.preventDefault(); apply(draft, status); }}>
      <Input className="pu-search" aria-label="Buscar por título, código o área" placeholder="Buscar por título, código o área" type="search"
        value={draft} maxLength={200} onChange={(_, data) => setDraft(data.value)} contentBefore={<SearchRegular aria-hidden />} />
      {!results && <div className="pu-select"><FilterRegular aria-hidden />
        <Select aria-label="Filtrar por estado" value={status} onChange={(_, data) => apply(draft, data.value as PublicStatus | '')}>
          <option value="">Todos los estados</option><option value="open">Abiertas</option>
          <option value="closed">Cerradas</option><option value="awarded">Adjudicadas</option>
        </Select></div>}
      <Button type="submit">Buscar</Button>
    </form>
    {query.isPending || query.isError ? <QueryNotice error={query.error} retry={() => void query.refetch()} loading="Consultando publicaciones…" />
      : query.data.items.length > 0 ? <div className="pu-cards">{query.data.items.map(tender => <TenderCard key={tender.code} tender={tender} />)}</div>
      : page > 1 ? <div className="pu-state"><strong>Esta página no tiene resultados.</strong><Button onClick={() => apply(search, status)}>Volver a la primera página</Button></div>
      : <EmptyList filtered={filtered} results={results} reset={() => apply('', '')} />}
    {query.data && totalPages > 1 && <nav className="pu-pager" aria-label="Páginas de resultados">
      <Button icon={<ChevronLeftRegular />} disabled={page <= 1} onClick={() => apply(search, status, page - 1)} aria-label="Página anterior" />
      <span>Página {page} de {totalPages}</span>
      <Button icon={<ChevronRightRegular />} disabled={page >= totalPages} onClick={() => apply(search, status, page + 1)} aria-label="Página siguiente" />
    </nav>}
  </section>;
}

export function PublicHomePage() {
  usePageTitle();
  return <div className="pu-page pu-home">
    <section className="pu-hero">
      <div className="pu-hero-inner">
        <span className="pu-hero-kicker"><span aria-hidden="true" /> Portal de proveedores</span>
        <h1>{APP_NAME}</h1>
        <p>Encontrá oportunidades para proveer a la Intendencia, presentá tu oferta y conocé cómo se adjudica cada compra.</p>
        <div className="pu-hero-actions"><a className="pu-hero-primary" href="#licitaciones">Explorar licitaciones<ArrowDownRegular /></a>
          <Link className="pu-hero-secondary" to="/resultados">Ver resultados<ArrowRightRegular /></Link></div>
      </div>
    </section>
    <TenderList />
  </div>;
}

export function PublicResultsPage() {
  usePageTitle('Resultados y transparencia');
  return <div className="pu-page">
    <Link className="pu-back" to="/"><ArrowLeftRegular />Volver al portal</Link>
    <header className="pu-banner"><div className="pu-banner-icon"><GavelRegular /></div><div>
      <h1>Resultados y transparencia</h1><p>La autoridad responsable publica su resolución junto con la evaluación de las ofertas.</p>
    </div></header>
    <TenderList results />
  </div>;
}
