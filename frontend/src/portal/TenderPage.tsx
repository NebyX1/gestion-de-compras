import { ArrowDownloadRegular, ArrowRightRegular, BuildingRegular, CalendarLtrRegular, CheckmarkCircleRegular, DocumentBulletListRegular, GavelRegular, LocationRegular, PersonRegular, ScalesRegular, SparkleRegular } from '@fluentui/react-icons';
import { useEffect, type ReactNode } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { formatBytes, formatDateTime, formatMoney } from '../lib/format';
import { tenderPath, useTender, type Award, type Tender } from './api';
import { BackLink, DemoMark, QueryNotice, Status, usePageTitle } from './shared';

const channelNames: Record<string, string> = {
  portal: 'Portal de proveedores', presencial: 'Recepción presencial', electronico_arce: 'Apertura electrónica ARCE',
  correo_pliego: 'Correo indicado en el pliego', otro: 'Canal indicado en el pliego',
};
const attributes: Record<string, string> = { delivery_days: 'Plazo de entrega (días)', warranty_months: 'Garantía (meses)' };
const comparisons: Record<string, string> = { gte: '≥', lte: '≤', gt: '>', lt: '<', eq: '=' };
const unitPrice = (value: string) => Number(value).toLocaleString('es-UY', { minimumFractionDigits: 2, maximumFractionDigits: 4 });

function Fact({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return <div className="pu-fact"><dt>{icon}{title}</dt><dd>{children}</dd></div>;
}

function AwardDetails({ award }: { award: Award }) {
  return <section className="pu-panel pu-award" id="resultado" aria-labelledby="pu-award-title">
    <header className="pu-panel-title"><GavelRegular /><h2 id="pu-award-title">Resultado de la adjudicación</h2></header>
    <div className="pu-winner"><div><small>Proveedor adjudicatario</small><h3>{award.supplier}</h3></div>
      <div><small>Importe adjudicado</small><strong>{formatMoney(award.amount, award.currency)}</strong></div></div>
    <dl className="pu-review-list"><div><dt>Resolución</dt><dd>{award.reference}</dd></div>
      <div><dt>Fecha de adjudicación</dt><dd>{formatDateTime(award.awarded_at)}</dd></div>
      <div><dt>Publicación del resultado</dt><dd>{formatDateTime(award.published_at)}</dd></div></dl>
    {award.lines.length > 0 && <details className="pu-details"><summary>Oferta ganadora por renglón</summary><div className="pu-table-wrap" tabIndex={0} role="region" aria-label="Detalle de la oferta ganadora">
      <table><thead><tr><th>Renglón</th><th>Cantidad</th><th>Precio unitario</th><th>IVA</th><th>Importe</th></tr></thead>
        <tbody>{award.lines.map((line, index) => <tr key={index}><td>{line.description}</td><td>{Number(line.quantity).toLocaleString('es-UY')} {line.unit}</td>
          <td>{award.currency} {unitPrice(line.unit_price)}</td><td>{Number(line.tax_rate)} %</td><td>{formatMoney(line.amount, award.currency)}</td></tr>)}</tbody>
      </table></div>
      {(Number(award.freight || 0) > 0 || Number(award.discount || 0) > 0) && <dl className="pu-review-list">
        {Number(award.freight || 0) > 0 && <div><dt>Flete con impuestos</dt><dd>{formatMoney(award.freight, award.currency)}</dd></div>}
        {Number(award.discount || 0) > 0 && <div><dt>Descuento global</dt><dd>{formatMoney(award.discount, award.currency)}</dd></div>}
      </dl>}
    </details>}
    <div className="pu-decision-block"><h3><PersonRegular />Decisión de la autoridad</h3><p>{award.grounds}</p>
      {typeof award.followed_recommendation === 'boolean' && <strong className="pu-decision-status">{award.followed_recommendation ? 'La decisión coincide con la recomendación del pliego.' : 'La autoridad se apartó de la recomendación del pliego.'}</strong>}
      {award.departure_reason && <p>{award.departure_reason}</p>}</div>
    {award.recommendation_reason && <div className="pu-decision-block"><h3><ScalesRegular />Evaluación según el pliego</h3>
      {award.recommended_supplier && <p>Proveedor recomendado: <b>{award.recommended_supplier}</b></p>}
      <p>{award.recommendation_reason}</p>
      {award.evaluation_version && <small>Versión de la evaluación: {award.evaluation_version}</small>}</div>}
    {award.ai_explanation && <div className="pu-decision-block"><h3><SparkleRegular />Recomendación inicial de la IA</h3>
      {award.ai_recommended_supplier && <p>Proveedor propuesto por la IA: <b>{award.ai_recommended_supplier}</b></p>}
      {award.ai_abstained && <p>La IA se abstuvo de recomendar un proveedor.</p>}
      <p>{award.ai_explanation}</p>
      {typeof award.followed_ai_recommendation === 'boolean' && <p><strong className="pu-decision-status">
        {award.followed_ai_recommendation ? 'La autoridad adjudicó al proveedor propuesto por la IA.' : 'La autoridad eligió un proveedor distinto del propuesto por la IA.'}
      </strong></p>}
      {award.ai_model && <small>Modelo: {award.ai_model}</small>}</div>}
  </section>;
}

function PurchaseDetails({ tender }: { tender: Tender }) {
  const { spec } = tender;
  return <>
    <section className="pu-panel"><header className="pu-panel-title"><DocumentBulletListRegular /><h2>Objeto de la compra</h2></header>
      <p className="pu-prose">{tender.need_text}</p>
      {tender.lines.length > 0 && <div className="pu-table-wrap" tabIndex={0} role="region" aria-label="Renglones solicitados"><table>
        <thead><tr><th>Renglón</th><th>Bien o servicio</th><th>Cantidad solicitada</th></tr></thead>
        <tbody>{tender.lines.map(line => <tr key={line.id}><td>{line.position}</td><td>{line.description}</td>
          <td>{Number(line.quantity).toLocaleString('es-UY', { maximumFractionDigits: 4 })} {line.unit}</td></tr>)}</tbody>
      </table></div>}
      {(tender.delivery_place || spec.delivery_terms) && <div className="pu-inset"><h3><LocationRegular />Entrega</h3>
        {tender.delivery_place && <p>{tender.delivery_place}</p>}{spec.delivery_terms && <p>{spec.delivery_terms}</p>}</div>}
    </section>
    <section className="pu-panel"><header className="pu-panel-title"><CheckmarkCircleRegular /><h2>Requisitos del pliego</h2></header>
      {spec.attachment && <a className="pu-download" href={spec.attachment.url} download={spec.attachment.filename}>
        <ArrowDownloadRegular /><span><strong>Descargar pliego</strong><small>{spec.attachment.filename} · Versión {spec.attachment.version} · {formatBytes(spec.attachment.size)}</small></span>
      </a>}
      {spec.minimum_text && <p className="pu-prose">{spec.minimum_text}</p>}
      {spec.requirements.length ? <ul className="pu-rules">{spec.requirements.map(req =>
        <li key={req.code}><span className="pu-code">{req.code}</span><div><strong>{req.text}</strong>
          {req.kind === 'numeric' && req.attribute && req.operator && req.threshold !== null && <p>
            {attributes[req.attribute] || req.attribute} {comparisons[req.operator] || req.operator} {Number(req.threshold).toLocaleString('es-UY')} {req.unit}</p>}
          {req.essential && <small>Requisito esencial</small>}</div></li>)}</ul> : !spec.minimum_text && <p>No se publicaron requisitos específicos.</p>}
    </section>
    <section className="pu-panel"><header className="pu-panel-title"><ScalesRegular /><h2>Criterios de evaluación</h2></header>
      {spec.mode === 'min_price' && <p>Se compara el precio de las ofertas que cumplen los requisitos del pliego.</p>}
      {spec.mode === 'framework' && <p>La compra se evalúa de acuerdo con las condiciones del convenio marco.</p>}
      {!!spec.criteria.length && <ul className="pu-criteria">{spec.criteria.map((criterion, i) => <li key={i}><div>
        <strong>{criterion.name}</strong>{criterion.description && <p>{criterion.description}</p>}
        {criterion.type === 'scale' && criterion.scale.length > 0 && <details className="pu-details"><summary>Escala de puntuación</summary>
          {criterion.attribute && <p>{attributes[criterion.attribute] || criterion.attribute}</p>}
          <ul>{criterion.scale.map((band, index) => <li key={index}>
            {band.max == null || band.max === '' ? `Desde ${band.min ?? 0}` : `De ${band.min ?? 0} a ${band.max}`}: {band.points} puntos
          </li>)}</ul></details>}</div><b>{Number(criterion.weight)} %</b></li>)}</ul>}
      {spec.mode === 'weighted' && !spec.criteria.length && <p>Este pliego no detalla los pesos de evaluación.</p>}
    </section>
  </>;
}

export function PublicTenderPage() {
  const { id = '' } = useParams();
  const query = useTender(id);
  const tender = query.data;
  const { hash } = useLocation();
  usePageTitle(tender?.title || 'Detalle de licitación');
  useEffect(() => {
    if (tender && hash === '#resultado') document.getElementById('resultado')?.scrollIntoView();
  }, [tender, hash]);
  return <div className="pu-page"><BackLink />
    {!tender ? <QueryNotice error={query.error} retry={() => void query.refetch()} loading="Cargando licitación…" /> : <>
      <header className="pu-heading"><div className="pu-heading-meta"><span className="pu-code">{tender.code}</span><Status tender={tender} /><DemoMark demo={tender.is_demo} /></div>
        <h1>{tender.title}</h1><p>{tender.procedure_label} · {tender.area}</p></header>
      <div className={tender.award ? 'pu-layout pu-awarded-layout' : 'pu-layout'}><div className="pu-main-panels">
        {tender.award && <AwardDetails award={tender.award} />}<PurchaseDetails tender={tender} />
      </div><aside className="pu-panel pu-aside"><h2>Datos del llamado</h2>
        <dl className="pu-facts"><Fact icon={<CalendarLtrRegular />} title="Publicado el">{formatDateTime(tender.published_at)}</Fact>
          {tender.deadline && <Fact icon={<CalendarLtrRegular />} title="Cierre de recepción">{formatDateTime(tender.deadline)}<small>Hora de Uruguay</small></Fact>}
          <Fact icon={<BuildingRegular />} title="Área convocante">{tender.area}</Fact>
          <Fact icon={<DocumentBulletListRegular />} title="Canal de recepción">{channelNames[tender.spec.reception_channel] || tender.spec.reception_channel}
            {tender.spec.reception_place && <small>{tender.spec.reception_place}</small>}</Fact>
        </dl>{tender.can_submit && <Link className="pu-primary-link" to={`${tenderPath(tender.code)}/ofertar`}>Presentar oferta<ArrowRightRegular /></Link>}
      </aside></div>
    </>}
  </div>;
}
