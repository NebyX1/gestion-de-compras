import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiApi, casesApi } from '../../api/endpoints';
import type { AiAdvice, CaseDetail, EvaluationOfferResult, Offer } from '../../api/types';
import { formatMoney } from '../../lib/format';
import { useSession } from '../../session';
import { Badge, Empty, ErrorNotice, Loading, Modal, Notice } from '../ui';

const STATES = {
  admissible: { label: 'Admisible', tone: 'green' },
  excluded: { label: 'Excluida', tone: 'red' },
  pending: { label: 'Pendiente', tone: 'amber' },
} as const;
const REQUIREMENTS = {
  met: { label: 'Cumple', tone: 'green' },
  not_met: { label: 'No cumple', tone: 'red' },
  pending: { label: 'Por verificar', tone: 'amber' },
} as const;

interface Row {
  id: number;
  name: string;
  offer?: Offer;
  result?: EvaluationOfferResult;
}

function offerName(name: string) {
  return name.replace(/ · demo$/, '');
}

function comparablePrice(row: Row, fallbackCurrency: string) {
  const totals = row.result?.totals;
  return totals?.comparable == null ? '—' : formatMoney(totals.comparable, totals.evaluation_currency ?? fallbackCurrency);
}

export function ComparisonPanel({ purchase }: { purchase: CaseDetail }) {
  const { can } = useSession();
  const { evaluation, offers, spec, offers_sealed: sealed } = purchase;
  const current = evaluation?.status === 'current' ? evaluation : null;
  const result = current?.result;
  const byId = new Map(offers.map((offer) => [offer.id, offer]));
  const rows: Row[] = (result?.offers ?? []).map((row) => ({
    id: row.id, name: offerName(row.name), offer: byId.get(row.id), result: row,
  }));
  const evaluated = new Set(rows.map((row) => row.id));
  rows.push(...offers.filter((offer) => !evaluated.has(offer.id)).map((offer) => ({
    id: offer.id, name: offerName(offer.supplier), offer,
  })));
  const winner = rows.find((row) => row.id === current?.recommended_offer_id && row.result?.status === 'admissible');
  const decisions = new Map(current?.offer_decisions?.map((decision) => [decision.offer_id, decision]));
  const weighted = current?.mode === 'weighted';
  const [detail, setDetail] = useState<'ai' | 'calculation' | null>(null);

  if (sealed) return <Notice tone="amber">Los sobres están reservados. Podrás comparar los precios después de la apertura.</Notice>;
  if (rows.length === 0 && !result) return <Empty title="Todavía no hay ofertas para comparar." />;

  const metrics: { title: string; hint: string; value: (row: Row) => string | number | null | undefined; label: (row: Row) => string }[] = [
    { title: 'Precio comparable', hint: 'Menor importe', value: (row) => row.result?.totals?.comparable,
      label: (row) => comparablePrice(row, purchase.currency) },
    { title: 'Entrega', hint: 'Menos días', value: (row) => row.offer?.data?.delivery_days,
      label: (row) => row.offer?.data?.delivery_days == null ? '—' : `${row.offer.data.delivery_days} días` },
    { title: 'Garantía', hint: 'Más meses', value: (row) => row.offer?.data?.warranty_months,
      label: (row) => row.offer?.data?.warranty_months == null ? '—' : `${row.offer.data.warranty_months} meses` },
  ];

  return (
    <div className="comparison-stack">
      <section className={`comparison-verdict${winner ? ' has-winner' : ''}`} aria-labelledby="comparison-verdict">
        <div>
          <div className="eyebrow">{winner ? '✓ Recomendación del cálculo' : 'Resultado de la comparación'}</div>
          <h2 id="comparison-verdict">{winner?.name ?? (result ? 'Sin recomendación' : 'Evaluación pendiente')}</h2>
          <p>{winner
            ? weighted
              ? `Es la oferta admisible con mayor puntaje según los criterios publicados: ${winner.result?.score_display} puntos.`
              : current?.mode === 'framework'
                ? 'Es la selección de convenio marco validada por el cálculo.'
                : 'Es la oferta admisible de menor importe comparable.'
            : evaluation?.status === 'stale'
              ? 'Los datos cambiaron. Es necesario recalcular la evaluación antes de recomendar.'
              : result ? 'Revisá los motivos antes de continuar.' : 'Las ofertas registradas se muestran sin orden de mérito hasta que se calcule la evaluación.'}</p>
          {!!result?.blocked_reasons.length && <ul className="helper-list">{result.blocked_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
          {result?.similar && <p>Las primeras ofertas tienen resultados cercanos. Revisá sus diferencias antes de decidir.</p>}
          <p className="small-text">La recomendación orienta. La adjudicación queda a cargo de la persona autorizada.</p>
        </div>
        {current && (
          <div className="comparison-verdict-actions">
            {can('ai.use') && (current.ai_advice || (winner && ['offers_opened', 'evaluation', 'decision'].includes(purchase.status))) &&
              <button type="button" className="btn" onClick={() => setDetail('ai')}>{current.ai_advice ? 'Ver recomendación de IA' : 'Solicitar recomendación de IA'}</button>}
            <button type="button" className="btn secondary" onClick={() => setDetail('calculation')}>Ver cálculo</button>
          </div>
        )}
      </section>

      {current?.ai_advice && <section className="card" aria-label="Criterio de la IA">
        <div className="eyebrow">Recomendación de IA</div>
        <h2>{current.ai_advice.supplier ?? 'El modelo se abstuvo'}</h2>
        <p className="ai-explanation">{current.ai_advice.reason}</p>
        <small>{current.ai_advice.model} · Evaluación {current.version}</small>
      </section>}
      {!current?.ai_advice && current?.ai_explanation && <details><summary>Explicación del cálculo generada por IA</summary>
        <p className="ai-explanation">{current.ai_explanation.content}</p></details>}

      <section aria-labelledby="supplier-overview">
        <div className="comparison-section-head"><h2 id="supplier-overview">Ofertas de un vistazo</h2><span>{rows.length} {rows.length === 1 ? 'oferta' : 'ofertas'}</span></div>
        <div className="comparison-grid">
          {rows.map((row) => {
            const status = row.result ? STATES[row.result.status] : null;
            const decision = decisions.get(row.id);
            const messages = decision?.items ?? [];
            const failedReviews = row.result?.status === 'excluded'
              ? (row.offer?.reviews ?? []).filter((review) => review.result === 'not_met' && review.note &&
                row.result?.requirements.some((requirement) => requirement.id === review.requirement_id && requirement.result === 'not_met'))
              : [];
            return (
              <article className={`card comparison-offer${winner?.id === row.id ? ' recommended' : ''}`} key={row.id}>
                <Badge tone={winner?.id === row.id ? 'purple' : status?.tone ?? 'neutral'}>
                  {winner?.id === row.id ? 'Recomendada' : status?.label ?? (row.offer?.data ? 'Sin evaluar' : 'Sin cotización')}
                </Badge>
                <h3>{row.name}</h3>
                {row.offer?.technical_description && <details><summary>Propuesta técnica</summary><p>{row.offer.technical_description}</p></details>}
                <div className="comparison-price">{comparablePrice(row, purchase.currency)}</div>
                <p className="small-text">Importe comparable{row.offer?.data?.freight != null
                  && ` · Flete declarado: ${formatMoney(row.offer.data.freight, row.offer.currency)}`}</p>
                <dl>
                  <div><dt>Entrega</dt><dd>{row.offer?.data?.delivery_days != null ? `${row.offer.data.delivery_days} días` : '—'}</dd></div>
                  <div><dt>Garantía</dt><dd>{row.offer?.data?.warranty_months != null ? `${row.offer.data.warranty_months} meses` : '—'}</dd></div>
                  {weighted && <div><dt>Puntaje</dt><dd>{row.result?.score_display ?? '—'}</dd></div>}
                </dl>
                <div className="comparison-reason">
                  <h4>{decision?.title ?? 'Todavía sin resultado'}</h4>
                  {messages[0] && <p>{messages[0]}</p>}
                  {!decision && <p>Esta oferta todavía no tiene un resultado vigente para explicar.</p>}
                  {messages.length > 1 && <ul className="helper-list">{messages.slice(1).map((message, i) => <li key={i}>{message}</li>)}</ul>}
                  {failedReviews.map((review) => <p key={review.requirement_id}><strong>Observación técnica:</strong> {review.note}</p>)}
                  {!!row.result?.warnings.length && <ul className="helper-list small-text">{row.result.warnings.map((message, i) => <li key={i}>{message}</li>)}</ul>}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {rows.length > 0 && (
        <section aria-labelledby="comparison-metrics">
          <div className="comparison-section-head"><h2 id="comparison-metrics">¿En qué se diferencian?</h2></div>
          <p className="muted">Las barras muestran valores, no el orden de mérito. Las ofertas excluidas no compiten.</p>
          <div className="comparison-grid">
            {metrics.map((metric) => {
              const maximum = rows.reduce((max, row) => Math.max(max, Number(metric.value(row) ?? 0)), 1);
              return (
              <article className="card comparison-chart" key={metric.title}>
                <h3>{metric.title}</h3><p className="small-text">{metric.hint}</p>
                <ul>
                  {rows.map((row) => {
                    const value = metric.value(row);
                    return (
                      <li key={row.id}>
                        <div className="chart-label"><span>{row.name}</span><strong>{metric.label(row)}</strong></div>
                        <div className="chart-track" aria-hidden="true"><span className={row.result?.status === 'excluded' ? 'excluded' : row.id === winner?.id ? 'leading' : ''} style={{ width: `${value == null ? 0 : (100 * Number(value) / maximum)}%` }} /></div>
                      </li>
                    );
                  })}
                </ul>
              </article>
              );
            })}
          </div>
        </section>
      )}

      {rows.length > 0 && spec && (
        <section className="card" aria-labelledby="requirements-heading">
          <div className="comparison-section-head"><h2 id="requirements-heading">Qué pide el pliego</h2></div>
          {spec.minimum_text && <p>{spec.minimum_text}</p>}
          {spec.criteria.length > 0 && <div className="row comparison-weights">{spec.criteria.map((criterion) => (
            <Badge key={criterion.code}>{criterion.name}: {criterion.weight} puntos posibles</Badge>
          ))}</div>}
          {(spec.requirements.length > 0 || (weighted && spec.criteria.length > 0)) && <div className="table-wrap comparison-matrix" tabIndex={0} role="region" aria-label="Cuadro de cumplimiento por proveedor">
            <table>
              <thead><tr><th scope="col">Requisito</th>{rows.map((row) => <th scope="col" key={row.id}>{row.name}</th>)}</tr></thead>
              <tbody>
                {spec.requirements.map((requirement) => (
                  <tr key={requirement.code}>
                    <th scope="row">{requirement.text}{requirement.essential && <span className="small-text">Excluyente</span>}</th>
                    {rows.map((row) => {
                      const review = row.result?.requirements.find((item) => item.code === requirement.code);
                      const state = review && (review.treatment === 'subsanable' && review.result === 'not_met'
                        ? { label: 'Pendiente de subsanar', tone: 'amber' } : REQUIREMENTS[review.result]);
                      return <td key={row.id}>{state ? <Badge tone={state.tone}>{state.label}</Badge> : 'Sin evaluar'}{review?.observed && <span className="small-text">{review.observed}{requirement.unit ? ` ${requirement.unit}` : ''}</span>}</td>;
                    })}
                  </tr>
                ))}
                {weighted && spec.criteria.map((criterion) => (
                  <tr key={criterion.code}>
                    <th scope="row">{criterion.name}<span className="small-text">Puntaje del criterio</span></th>
                    {rows.map((row) => {
                      const points = row.result?.criteria.find((item) => item.code === criterion.code);
                      return <td key={row.id}>{points ? `${Number(points.points).toLocaleString('es-UY', { maximumFractionDigits: 2 })} / ${points.max}` : '—'}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
        </section>
      )}

      {detail === 'ai' && current && <RecommendationDialog key={current.id} code={purchase.code} evaluationId={current.id} initial={current.ai_advice} onClose={() => setDetail(null)} />}
      {detail === 'calculation' && <Calculation code={purchase.code} onClose={() => setDetail(null)} />}
    </div>
  );
}

function RecommendationDialog({ code, evaluationId, initial, onClose }: { code: string; evaluationId: number; initial?: AiAdvice | null; onClose: () => void }) {
  const client = useQueryClient();
  const explanation = useMutation({ mutationFn: () => aiApi.recommend(code), onSuccess: () => client.invalidateQueries({ queryKey: ['case', code] }) });
  const draft = initial ?? explanation.data;
  return (
    <Modal title="Recomendación de IA" onClose={onClose} footer={
      draft ? <button type="button" className="btn" onClick={onClose}>Listo</button> :
        <button type="button" className="btn" disabled={explanation.isPending} onClick={() => explanation.mutate()}>
          {explanation.isPending ? 'Generando…' : 'Confirmar y consultar'}
        </button>
    }>
      <div className="stack">
        {!draft && <Notice tone="blue">Al confirmar, el modelo recibirá los criterios del pliego y los datos de las ofertas admisibles bajo alias. Comparará puntajes, precios relativos, plazos y garantías. Su recomendación inicial quedará registrada para la decisión humana.</Notice>}
        {explanation.isPending && <Loading label="Comparando las ofertas admisibles…" />}
        {explanation.isError && <><ErrorNotice error={explanation.error} /><p>El cálculo y su recomendación siguen disponibles.</p></>}
        {draft && (draft.evaluation_id === evaluationId ? (
          <>
            <h3>{draft.supplier ?? 'El modelo se abstuvo de recomendar una oferta'}</h3>
            <p className="ai-explanation">{draft.reason}</p>
            <p className="small-text">{draft.model} · La autoridad competente decide la adjudicación.</p>
          </>
        ) : <Notice tone="amber">La evaluación cambió. Actualizá la compra antes de usar la explicación.</Notice>)}
      </div>
    </Modal>
  );
}

function Calculation({ code, onClose }: { code: string; onClose: () => void }) {
  const query = useQuery({ queryKey: ['case-explanation', code], queryFn: () => casesApi.explanation(code) });
  return (
    <Modal title="Cómo se calculó" onClose={onClose} wide>
      {query.isPending && <Loading />}
      {query.isError && <ErrorNotice error={query.error} />}
      {query.data?.sections.map((section) => (
        <section key={section.heading}>
          <h3>{section.heading}</h3>
          <ul className="helper-list">{section.items.map((item, i) => <li key={i}>{item}</li>)}</ul>
        </section>
      ))}
    </Modal>
  );
}
