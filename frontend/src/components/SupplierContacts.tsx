import { useState, type FormEvent } from 'react';
import { Button, Field, Input, Select } from '@fluentui/react-components';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { organizationApi } from '../api/endpoints';
import type { Supplier } from '../api/types';
import { Empty, ErrorNotice, Loading, Modal, useToast } from './ui';

type Edit = { supplier: Supplier; kind: 'contact' | 'rupe' };
const rupeLabels: Record<string, string> = { activo: 'Activo', en_ingreso: 'En ingreso', suspendido: 'Suspendido', baja: 'Baja' };

export function SupplierContacts() {
  const [input, setInput] = useState('');
  const [search, setSearch] = useState('');
  const [edit, setEdit] = useState<Edit | null>(null);
  const result = useQuery({ queryKey: ['suppliers', search], queryFn: () => organizationApi.suppliers(search) });
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Montevideo' }).format(new Date());

  function find(event: FormEvent) {
    event.preventDefault();
    setSearch(input.trim());
  }

  return <div className="stack">
    <header><h1>Proveedores</h1><p>Consultá el contacto que recibe los códigos del portal y las constancias del RUPE.</p></header>
    <form onSubmit={find} className="row">
      <Field label="Buscar por razón social o identificador fiscal">
        <Input type="search" value={input} maxLength={80} onChange={(_, data) => setInput(data.value)} />
      </Field>
      <Button type="submit" appearance="primary">Buscar</Button>
    </form>
    {result.isPending && <Loading />}
    {result.isError && <ErrorNotice error={result.error} />}
    {result.data?.items.length === 0 && <Empty title="No se encontraron proveedores." />}
    {result.data && result.data.items.length > 0 && <section className="card">
      <div className="table-wrap"><table>
        <thead><tr><th>Proveedor</th><th>Correo registrado</th><th>Estado RUPE vigente</th><th>Acciones</th></tr></thead>
        <tbody>{result.data.items.map((supplier) => {
          const rupe = supplier.statuses?.find((s) => s.kind === 'rupe' && (!s.valid_from || s.valid_from <= today) && (!s.valid_to || s.valid_to >= today));
          return <tr key={supplier.id}>
            <td><strong>{supplier.name}</strong><div className="muted small-text">{supplier.tax_id ?? supplier.code}</div></td>
            <td>{supplier.contact_email ?? 'Sin registrar'}</td>
            <td>{rupe ? (rupeLabels[rupe.state] ?? rupe.state) : 'Sin constancia'}{rupe && <div className="muted small-text">{rupe.evidence_ref}</div>}</td>
            <td><div className="row">
              <Button size="small" onClick={() => setEdit({ supplier, kind: 'contact' })}>Editar contacto</Button>
              <Button size="small" onClick={() => setEdit({ supplier, kind: 'rupe' })}>Registrar RUPE</Button>
            </div></td>
          </tr>;
        })}</tbody>
      </table></div>
      {result.data.items.length === 200 && <p className="small-text">Se muestran los primeros 200 proveedores. Refiná la búsqueda.</p>}
    </section>}
    {edit && <SupplierEdit edit={edit} onClose={() => setEdit(null)} />}
  </div>;
}

function SupplierEdit({ edit: { supplier, kind }, onClose }: { edit: Edit; onClose: () => void }) {
  const contact = kind === 'contact';
  const [email, setEmail] = useState(supplier.contact_email ?? '');
  const [reference, setReference] = useState('');
  const [rupe, setRupe] = useState('activo');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const queryClient = useQueryClient();
  const notify = useToast();
  const mutation = useMutation({
    mutationFn: () => contact
      ? organizationApi.supplierContact(supplier.id, email.trim(), supplier.contact_email, reference.trim())
      : organizationApi.supplierStatus(supplier.id, { kind: 'rupe', state: rupe, valid_from: since || null, valid_to: until || null, evidence_ref: reference.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      notify(contact ? 'Contacto actualizado.' : 'Constancia RUPE registrada.');
      onClose();
    },
  });
  return <Modal title={contact ? 'Editar contacto' : 'Registrar constancia RUPE'} onClose={onClose}>
    <form className="stack" onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}>
      <strong>{supplier.name}</strong>
      {contact ? <Field label="Correo verificado del proveedor" required hint="El portal enviará los próximos códigos a esta dirección.">
        <Input type="email" value={email} maxLength={120} required onChange={(_, d) => setEmail(d.value)} />
      </Field> : <>
        <Field label="Estado que figura en la constancia" required>
          <Select value={rupe} onChange={(_, d) => setRupe(d.value)}>
            {Object.entries(rupeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </Field>
        <Field label="Vigente desde"><Input type="date" value={since} max={until || undefined} onChange={(_, d) => setSince(d.value)} /></Field>
        <Field label="Vigente hasta"><Input type="date" min={since || undefined} value={until} onChange={(_, d) => setUntil(d.value)} /></Field>
      </>}
      <Field label={contact ? 'Referencia del respaldo del contacto' : 'Referencia de la constancia RUPE'} required>
        <Input required minLength={3} maxLength={200} value={reference} onChange={(_, d) => setReference(d.value)} />
      </Field>
      {mutation.isError && <ErrorNotice error={mutation.error} />}
      <div className="row"><Button type="submit" appearance="primary" disabled={mutation.isPending}>
        {mutation.isPending ? 'Guardando…' : 'Guardar'}
      </Button><Button type="button" onClick={onClose}>Cancelar</Button></div>
    </form>
  </Modal>;
}
