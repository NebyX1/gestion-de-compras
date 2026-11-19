import { Button, Checkbox, Field, Input, Textarea } from '@fluentui/react-components';
import { ArrowLeftRegular, ArrowRightRegular, CheckmarkCircleRegular, CheckmarkRegular, ClipboardTaskRegular, MailRegular, PrintRegular, SendRegular } from '@fluentui/react-icons';
import { useMutation } from '@tanstack/react-query';
import { useRef, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toApiError } from '../api/client';
import { formatDateTime, formatMoney, uuid } from '../lib/format';
import { sendCode, submitOffer, tenderPath, useTender, type Contact, type OfferPayload, type OfferReceipt, type Tender } from './api';
import { BackLink, DemoMark, QueryNotice, usePageTitle } from './shared';

const steps = ['Proveedor', 'Propuesta', 'Confirmación'];
type QuoteLine = OfferPayload['lines'][number];
interface Proposal {
  lines: QuoteLine[];
  prices_include_tax: boolean;
  freight: string;
  delivery_days: string;
  warranty_months: string;
  technical_description: string;
}

function OfferLineFields({ tender, proposal, change }: { tender: Tender; proposal: Proposal; change: (value: Proposal) => void }) {
  function changeLine(id: number, field: 'unit_price' | 'tax_rate', value: string) {
    change({ ...proposal, lines: proposal.lines.map(line => line.request_line_id === id ? { ...line, [field]: value } : line) });
  }
  return <>
    <Checkbox label="Los precios unitarios ya incluyen impuestos" checked={proposal.prices_include_tax}
      onChange={(_, data) => change({ ...proposal, prices_include_tax: data.checked === true })} />
    {tender.lines.map((line, i) => <fieldset key={line.id} className="pu-line-input"><legend>Renglón {line.position} · {line.description}</legend>
      <p>Cantidad solicitada: {Number(line.quantity).toLocaleString('es-UY', { maximumFractionDigits: 4 })} {line.unit}</p>
      <div className="pu-form-grid">
        <Field label={`Precio unitario (${tender.currency})`} required><Input required type="number" min="0.0001" step="0.0001"
          value={proposal.lines[i].unit_price} onChange={(_, data) => changeLine(line.id, 'unit_price', data.value)} /></Field>
        <Field label="IVA (%)" required><Input required type="number" min="0" max="100" step="0.001"
          value={proposal.lines[i].tax_rate} onChange={(_, data) => changeLine(line.id, 'tax_rate', data.value)} /></Field>
      </div>
    </fieldset>)}
  </>;
}

function Review({ tender, contact, proposal, file }: { tender: Tender; contact: Contact; proposal: Proposal; file: File | null }) {
  return <><div className="pu-inset"><h3>{contact.supplier_name}</h3><p>{contact.tax_id} · {contact.email}</p></div>
    <div className="pu-table-wrap" role="region" aria-label="Cotización que se enviará" tabIndex={0}><table>
      <thead><tr><th>Renglón</th><th>Cantidad</th><th>Precio unitario ({tender.currency})</th><th>IVA</th></tr></thead>
      <tbody>{tender.lines.map((line, i) => <tr key={line.id}><td>{line.description}</td><td>{Number(line.quantity).toLocaleString('es-UY', { maximumFractionDigits: 4 })} {line.unit}</td>
        <td>{Number(proposal.lines[i].unit_price).toLocaleString('es-UY', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</td>
        <td>{Number(proposal.lines[i].tax_rate).toLocaleString('es-UY', { maximumFractionDigits: 3 })} %</td></tr>)}</tbody>
    </table></div>
    <dl className="pu-review-list"><div><dt>Precios unitarios</dt><dd>{proposal.prices_include_tax ? 'Con impuestos incluidos' : 'Sin impuestos incluidos'}</dd></div>
      <div><dt>Flete con impuestos</dt><dd>{formatMoney(proposal.freight || '0', tender.currency)}</dd></div>
      <div><dt>Entrega</dt><dd>{proposal.delivery_days} días</dd></div><div><dt>Garantía</dt><dd>{proposal.warranty_months || '0'} meses</dd></div>
      {file && <div><dt>Archivo adjunto</dt><dd>{file.name}</dd></div>}</dl>
    <h3>Descripción técnica</h3><p className="pu-prose">{proposal.technical_description}</p>
  </>;
}

function Receipt({ receipt, tender }: { receipt: OfferReceipt; tender: Tender }) {
  return <div className="pu-panel pu-receipt"><div className="pu-receipt-icon"><CheckmarkCircleRegular /></div>
    <h1>Oferta recibida</h1><p>Guardá el comprobante de presentación de tu oferta.</p><div className="pu-inset">
      <small>Número de comprobante</small><strong className="pu-receipt-code">{receipt.receipt_code}</strong></div>
    <dl className="pu-review-list"><div><dt>Licitación</dt><dd>{receipt.tender_code} · {tender.title}</dd></div>
      <div><dt>Recepción (hora de Uruguay)</dt><dd>{formatDateTime(receipt.received_at)}</dd></div></dl>
    <div className="pu-receipt-actions"><Button icon={<PrintRegular />} onClick={() => window.print()}>Imprimir comprobante</Button>
      <Link className="pu-card-link" to={tenderPath(tender.code)}>Volver a la licitación<ArrowRightRegular /></Link></div>
  </div>;
}

function OfferWizard({ tender }: { tender: Tender }) {
  const [step, setStep] = useState(0);
  const [contact, setContact] = useState<Contact>({ supplier_name: '', tax_id: '', email: '' });
  const [proposal, setProposal] = useState<Proposal>(() => ({
    lines: tender.lines.map(line => ({ request_line_id: line.id, unit_price: '', tax_rate: '' })),
    prices_include_tax: false, freight: '0', delivery_days: '', warranty_months: '0', technical_description: '',
  }));
  const [file, setFile] = useState<File | null>(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [formError, setFormError] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const [idempotencyKey] = useState(uuid);
  const verify = useMutation({ mutationFn: () => sendCode(tender.code, contact) });
  const send = useMutation({
    mutationFn: () => submitOffer(tender.code, {
      ...contact, supplier_name: contact.supplier_name.trim(), tax_id: contact.tax_id.trim(), email: contact.email.trim(), ...proposal,
      technical_description: proposal.technical_description.trim(), delivery_days: Number(proposal.delivery_days),
      warranty_months: Number(proposal.warranty_months || 0), freight: proposal.freight || '0',
      spec_id: tender.spec.id, verification_code: verificationCode.trim(), accepted_terms: accepted,
    }, idempotencyKey, file),
  });
  const pending = send.isPending || verify.isPending;
  const serverError = send.error || verify.error;
  const error = serverError ? toApiError(serverError) : null;

  function goto(next: number) {
    setStep(next);
    if (next < 2) setAccepted(false);
    setFormError('');
    send.reset();
    requestAnimationFrame(() => heading.current?.focus());
  }
  function changeContact(field: keyof Contact, value: string) {
    setContact({ ...contact, [field]: value });
    if (field === 'tax_id' || field === 'email') {
      verify.reset();
      setVerificationCode('');
    }
  }
  function advance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (step === 0 && contact.supplier_name.trim().length < 3) return setFormError('Ingresá la razón social completa.');
    if (step === 0 && contact.tax_id.replace(/[.-]/g, '').length < 5) return setFormError('El identificador fiscal debe incluir al menos cinco letras o números.');
    if (step === 0 && !/^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$/.test(contact.email)) return setFormError('Revisá el correo del proveedor, incluido el dominio.');
    if (step === 1 && proposal.technical_description.trim().length < 10) return setFormError('Describí la propuesta técnica con al menos 10 caracteres.');
    if (step < 2) return goto(step + 1);
    if (!accepted || !verify.isSuccess) return setFormError('Solicitá el código por correo y confirmá los datos para enviar.');
    setFormError('');
    send.mutate();
  }

  if (send.data) return <Receipt receipt={send.data} tender={tender} />;
  return <>
    <header className="pu-heading"><div className="pu-heading-meta"><span className="pu-code">{tender.code}</span><DemoMark demo={tender.is_demo} /></div>
      <h1>Presentar oferta</h1><p>{tender.title}</p></header>
    <div className="pu-wizard-layout"><aside className="pu-panel pu-wizard-aside">
      <h2>Tu presentación</h2><ol className="pu-step-list">{steps.map((name, i) => <li key={name} aria-current={i === step ? 'step' : undefined} data-complete={i < step}>
        <span>{i < step ? <CheckmarkRegular aria-label="Completado" /> : i + 1}</span>
        <b>{name}</b></li>)}</ol>
      {tender.deadline && <div className="pu-deadline"><strong>Cierre de recepción</strong><span>{formatDateTime(tender.deadline)}</span><small>Hora de Uruguay</small></div>}
    </aside><form className="pu-panel pu-form" onSubmit={advance}>
      <header><small>Paso {step + 1} de {steps.length}</small>
        <h2 ref={heading} tabIndex={-1}>{['Datos del proveedor', 'Propuesta técnica y económica', 'Revisión y envío'][step]}</h2></header>
      {step === 0 && <div className="pu-form-fields">
        <Field label="Razón social" required><Input autoComplete="organization" value={contact.supplier_name} minLength={3} maxLength={200} required onChange={(_, d) => changeContact('supplier_name', d.value)} /></Field>
        <Field label="RUT o identificación fiscal" hint="De 5 a 30 caracteres. Podés usar letras, números, puntos y guiones." required>
          <Input value={contact.tax_id} required maxLength={30} pattern={'[A-Za-z0-9.\\-]{5,30}'} onChange={(_, d) => changeContact('tax_id', d.value)} /></Field>
        <Field label="Correo del proveedor" hint="Si tu empresa ya está registrada, usá su correo de contacto. Allí recibirás el código de presentación." required>
          <Input type="email" autoComplete="email" value={contact.email} required maxLength={120} onChange={(_, d) => changeContact('email', d.value)} /></Field>
      </div>}
      {step === 1 && <div className="pu-form-fields">
        <OfferLineFields tender={tender} proposal={proposal} change={setProposal} />
        <Field label={`Flete con impuestos incluidos (${tender.currency})`}><Input type="number" min="0" step="0.01"
          value={proposal.freight} onChange={(_, d) => setProposal({ ...proposal, freight: d.value })} /></Field>
        <div className="pu-form-grid"><Field label="Plazo de entrega (días)" required><Input required type="number" min="0" max="3650" step="1"
          value={proposal.delivery_days} onChange={(_, d) => setProposal({ ...proposal, delivery_days: d.value })} /></Field>
          <Field label="Garantía (meses)"><Input type="number" min="0" max="1200" step="1"
            value={proposal.warranty_months} onChange={(_, d) => setProposal({ ...proposal, warranty_months: d.value })} /></Field></div>
        <Field label="Descripción técnica" hint="Describí los bienes o servicios y cómo cumplen los requisitos del pliego." required>
          <Textarea required rows={5} minLength={10} maxLength={4000} value={proposal.technical_description} onChange={(_, d) => setProposal({ ...proposal, technical_description: d.value })} /></Field>
        <Field label={{ children: 'Documento de respaldo', htmlFor: 'pu-offer-file' }}
          hint={{ children: 'Opcional. PDF, JPG, PNG o TXT de hasta 8 MiB.', id: 'pu-offer-file-hint' }}>
          <input id="pu-offer-file" aria-describedby="pu-offer-file-hint" type="file" accept=".pdf,.jpg,.jpeg,.png,.txt" onChange={e => {
            const selected = e.target.files?.[0];
            if (!selected) { e.target.setCustomValidity(''); setFile(null); return; }
            if (selected.size > 8 * 1024 * 1024 || !/\.(pdf|jpe?g|png|txt)$/i.test(selected.name)) {
              e.target.setCustomValidity('Elegí un PDF, JPG, PNG o TXT de hasta 8 MiB.'); e.target.reportValidity(); setFile(null);
            } else { e.target.setCustomValidity(''); setFile(selected); }
          }} /></Field>
        {file && <div className="pu-file"><span>Archivo seleccionado: {file.name}</span><Button size="small" type="button" onClick={e => {
          const input = e.currentTarget.form?.querySelector<HTMLInputElement>('input[type=file]');
          if (input) { input.value = ''; input.setCustomValidity(''); }
          setFile(null);
        }}>Quitar</Button></div>}
      </div>}
      {step === 2 && <><Review tender={tender} contact={contact} proposal={proposal} file={file} />
        <div className="pu-verify"><h3><MailRegular />Verificación por correo</h3>
          <p>Solicitá un código para confirmar la presentación.</p>
          <Button type="button" disabled={pending} onClick={() => { setVerificationCode(''); send.reset(); verify.mutate(); }}>
            {verify.isPending ? 'Enviando código…' : verify.isSuccess ? 'Solicitar otro código' : 'Enviar código por correo'}</Button>
          {verify.isSuccess && <><p role="status">{verify.data.message}</p>
            <Field label="Código de 6 dígitos" required><Input value={verificationCode} inputMode="numeric" autoComplete="one-time-code" required
              maxLength={6} pattern="[0-9]{6}" onChange={(_, d) => setVerificationCode(d.value)} /></Field></>}
        </div>
        <Checkbox checked={accepted} onChange={(_, d) => setAccepted(d.checked === true)} label="Revisé la oferta y acepto las condiciones del pliego de esta licitación." />
      </>}
      {(error || formError) && <div role="alert" className="pu-error">{formError || error?.message}
        {error && Object.keys(error.fields).length > 0 && <ul>{Object.entries(error.fields).map(([key, message]) => <li key={key}>{message}</li>)}</ul>}</div>}
      <div className="pu-form-actions">
        {step > 0 && <Button icon={<ArrowLeftRegular />} disabled={pending} type="button" onClick={() => goto(step - 1)}>Atrás</Button>}
        <Button appearance="primary" type="submit" disabled={pending || (step === 2 && (!verify.isSuccess || !accepted || verificationCode.length !== 6))}
          icon={step === 2 ? <SendRegular /> : <ArrowRightRegular />} iconPosition="after">
          {send.isPending ? 'Presentando…' : step === 2 ? 'Confirmar y presentar' : 'Continuar'}</Button>
      </div>
    </form></div>
  </>;
}

export function PublicOfferPage() {
  const { id = '' } = useParams();
  const query = useTender(id);
  usePageTitle('Presentar oferta');
  return <div className="pu-page"><BackLink code={id} />
    {query.isPending || query.isError ? <QueryNotice error={query.error} retry={() => void query.refetch()} loading="Cargando formulario…" />
      : !query.data.can_submit ? <div className="pu-state"><ClipboardTaskRegular /><h1>Presentación en línea no disponible</h1>
        <p>Consultá el estado, el plazo y el canal de recepción de este llamado.</p>
        <Link className="pu-card-link" to={tenderPath(id)}>Ver licitación<ArrowRightRegular /></Link></div>
        : <OfferWizard key={query.data.code + ':' + query.data.spec.id} tender={query.data} />}
  </div>;
}
