import { Button, Spinner } from '@fluentui/react-components';
import { ArrowLeftRegular, ArrowRightRegular, BuildingRegular, CalendarLtrRegular, DocumentBulletListRegular, SearchRegular, WarningRegular } from '@fluentui/react-icons';
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { toApiError } from '../api/client';
import { APP_NAME } from '../lib/branding';
import { formatDateTime } from '../lib/format';
import { tenderPath, type TenderSummary } from './api';

export function usePageTitle(title?: string) {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME;
    return () => { document.title = previous; };
  }, [title]);
}

export function BackLink({ code }: { code?: string }) {
  return <Link className="pu-back" to={code ? tenderPath(code) : '/#licitaciones'}>
    <ArrowLeftRegular />{code ? 'Volver a la licitación' : 'Volver a las licitaciones'}
  </Link>;
}

export function Status({ tender }: { tender: TenderSummary }) {
  return <span className={`pu-status pu-status-${tender.status}`}><i aria-hidden="true" />{tender.status_label}</span>;
}

export function DemoMark({ demo }: { demo: boolean }) {
  return demo ? <span className="pu-demo">Demostración</span> : null;
}

export function QueryNotice({ error, retry, loading = 'Cargando…' }: { error?: unknown; retry?: () => void; loading?: string }) {
  if (!error) return <div className="pu-state" role="status"><Spinner size="small" label={loading} /></div>;
  return <div className="pu-state" role="alert"><WarningRegular aria-hidden /><strong>{toApiError(error).message}</strong>
    {retry && <Button onClick={retry}>Volver a intentar</Button>}</div>;
}

export function EmptyList({ filtered, results, reset }: { filtered: boolean; results: boolean; reset: () => void }) {
  return <div className="pu-state"><span className="pu-empty-icon">{filtered ? <SearchRegular /> : <DocumentBulletListRegular />}</span>
    <strong>{filtered ? 'No se encontraron coincidencias' : results ? 'Aún no hay adjudicaciones publicadas' : 'Aún no hay licitaciones publicadas'}</strong>
    <p>{filtered ? 'Probá con otro término o cambiá los filtros.' : results ? 'Los resultados aparecerán aquí cuando se publique la decisión final.' : 'Las próximas convocatorias de la Intendencia aparecerán aquí.'}</p>
    {filtered && <Button onClick={reset}>Limpiar búsqueda y filtros</Button>}</div>;
}

export function TenderCard({ tender }: { tender: TenderSummary }) {
  return <article className="pu-tender-card">
    <div className="pu-card-top"><span className="pu-symbol"><DocumentBulletListRegular /></span><Status tender={tender} /></div>
    <div className="pu-kicker"><span>{tender.code}</span><DemoMark demo={tender.is_demo} /></div>
    <h3><Link to={tenderPath(tender.code)}>{tender.title}</Link></h3>
    <p className="pu-kind">{tender.procedure_label}</p>
    <div className="pu-card-meta"><span><BuildingRegular />{tender.area}</span>
      {tender.deadline && <span><CalendarLtrRegular />Cierre {formatDateTime(tender.deadline)}</span>}</div>
    <Link className="pu-card-link" to={tenderPath(tender.code)} aria-label={`${tender.status === 'awarded' ? 'Ver resultado' : 'Ver licitación'} de ${tender.title}`}>
      {tender.status === 'awarded' ? 'Ver resultado' : 'Ver licitación'}<ArrowRightRegular /></Link>
  </article>;
}
