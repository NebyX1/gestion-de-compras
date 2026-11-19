import { useQueries, useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { casesApi } from '../api/endpoints';
import type { CaseSummary } from '../api/types';
import { Badge, Empty, ErrorNotice, Loading } from '../components/ui';
import { ComparisonPanel } from '../components/case/ComparisonPanel';
import { formatMoney } from '../lib/format';
import { STAGE_LABELS } from '../lib/labels';

// Etapas 2 (Ofertas), 3 (Evaluación) y 4 (Decisión), índices según STAGE_LABELS.
const EVALUATION_STAGES = [2, 3, 4];

export function EvaluatePage() {
  const results = useQueries({
    queries: EVALUATION_STAGES.map((stage) => ({
      queryKey: ['cases', { filter: 'active', stage, per_page: 50 }],
      queryFn: () => casesApi.list({ filter: 'active', stage, per_page: 50 }),
    })),
  });

  const loading = results.some((r) => r.isPending);
  const failed = results.find((r) => r.isError);
  const cases: CaseSummary[] = results.flatMap((r) => r.data?.items ?? []);
  const truncated = results.some((r) => (r.data?.total ?? 0) > (r.data?.items.length ?? 0));

  return (
    <>
      <header className="comparison-intro">
        <div>
          <div className="eyebrow">Compras de Lavalleja</div>
          <h1>Compará las ofertas</h1>
          <p>Elegí una compra y mirá qué ofrece cada proveedor, qué requisitos cumple y cuál recomienda el cálculo.</p>
        </div>
      </header>

      {loading && <Loading />}
      {failed && failed.error && <ErrorNotice error={failed.error} />}
      {!loading && !failed && cases.length === 0 && (
        <Empty title="No hay compras en evaluación.">
          Cuando una compra tenga ofertas registradas aparecerá aquí.
        </Empty>
      )}
      {!loading && cases.length > 0 && (
        <section className="comparison-grid" aria-label="Compras por comparar">
          {cases.map((c) => (
            <Link className="card comparison-case" key={c.code} to={`/evaluar/${encodeURIComponent(c.code)}`}>
              <div className="row"><Badge tone={c.tone}>{STAGE_LABELS[c.stage] ?? c.stage_label}</Badge>{c.is_demo && <Badge tone="neutral">Ejemplo</Badge>}</div>
              <span className="small-text">{c.code} · {c.area}</span>
              <h2>{c.title}</h2>
              <p>{c.estimated_total ? `Estimado: ${formatMoney(c.estimated_total, c.currency)}` : 'Sin monto estimado'}</p>
              <strong>Comparar ofertas <span aria-hidden="true">→</span></strong>
            </Link>
          ))}
        </section>
      )}
      {truncated && (
        <p className="small-text muted" style={{ marginTop: 10 }}>
          Se muestran las primeras 50 compras por etapa. Usá el listado de compras para ver el resto.
        </p>
      )}
    </>
  );
}

export function ComparisonPage() {
  const { code = '' } = useParams();
  const query = useQuery({ queryKey: ['case', code], queryFn: () => casesApi.get(code) });
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorNotice error={query.error} />;
  const purchase = query.data;
  return (
    <>
      <Link to="/evaluar" className="text-btn">← Todas las comparaciones</Link>
      <header className="page-heading comparison-heading">
        <div>
          <div className="eyebrow">{purchase.code} · {purchase.area}</div>
          <h1>{purchase.title}</h1>
          <p>{purchase.need_text}</p>
        </div>
        <div className="row">
          {purchase.is_demo && <Badge tone="blue">Datos de prueba</Badge>}
          <Link className="btn secondary" to={`/compras/${encodeURIComponent(code)}`}>Abrir expediente</Link>
        </div>
      </header>
      <ComparisonPanel key={code} purchase={purchase} />
    </>
  );
}
