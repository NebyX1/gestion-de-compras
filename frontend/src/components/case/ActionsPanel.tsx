import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { casesApi } from '../../api/endpoints';
import { isConflict, toApiError } from '../../api/client';
import type { ActionInfo, CaseDocument } from '../../api/types';
import { Badge, ErrorNotice, Modal, Notice, useToast } from '../ui';
import { DynamicForm, buildPayload, initialValues, validateValues, type FormErrors, type FormValues } from '../DynamicForm';
import { joinResponsible, uuid } from '../../lib/format';
import { invalidateCase } from './caseQueries';

interface ActionsPanelProps {
  code: string;
  version: number;
  actions: ActionInfo[];
  documents: CaseDocument[];
  nextAction?: string;
}

export function ActionsPanel({ code, version, actions, documents, nextAction }: ActionsPanelProps) {
  const [open, setOpen] = useState<ActionInfo | null>(null);

  if (actions.length === 0) {
    return <p className="muted">No hay acciones disponibles para tu rol en esta etapa.</p>;
  }

  const enabled = (action: ActionInfo) => action.can && !action.done && action.blockers.length === 0;
  const primary = actions.find((a) => a.name === nextAction && enabled(a) && !a.danger);
  const other = actions.filter((a) => a !== primary);
  return (
    <div className="stack">
      {primary && <div>
        <p>{primary.description}</p>
        <button type="button" className="btn" onClick={() => setOpen(primary)}>{primary.label}</button>
      </div>}
      {other.length > 0 && <details className="disclosure">
        <summary>{primary ? 'Otras acciones' : 'Ver acciones y sus condiciones'} ({other.length})</summary>
        <ul className="action-list">
          {other.map((a) => <li key={a.name}>
            <div>
              <strong>{a.label}</strong>
              <p className="small-text">{a.description} · {joinResponsible(a.responsible)}</p>
              {a.blockers.length > 0 && <ul className="helper-list small-text">{a.blockers.map((b) => <li key={b}>{b}</li>)}</ul>}
            </div>
            {enabled(a) ? <button type="button" className={`btn small ${a.danger ? 'danger' : 'secondary'}`} onClick={() => setOpen(a)}>Abrir <span className="sr-only">{a.label}</span></button>
              : <Badge tone={a.done ? 'green' : 'neutral'}>{a.done ? 'Completada' : 'No disponible'}</Badge>}
          </li>)}
        </ul>
      </details>}
      {open && (
        <ActionModal
          key={open.name}
          code={code}
          version={version}
          action={open}
          documents={documents}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}

interface ActionModalProps {
  code: string;
  version: number;
  action: ActionInfo;
  documents: CaseDocument[];
  onClose: () => void;
}

function ActionModal({ code, version, action, documents, onClose }: ActionModalProps) {
  const queryClient = useQueryClient();
  const notify = useToast();
  const [idempotencyKey] = useState(() => uuid());
  const [values, setValues] = useState<FormValues>(() => initialValues(action.form));
  const [errors, setErrors] = useState<FormErrors>({});
  const [formError, setFormError] = useState<unknown>(null);

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => casesApi.action(code, action.name, body),
    onSuccess: async () => {
      await invalidateCase(queryClient, code);
      notify(`${action.label}: registrado.`);
      onClose();
    },
    onError: async (err) => {
      if (isConflict(err)) {
        notify('La compra cambió mientras trabajabas en ella. Actualizamos el expediente; revisalo antes de volver a intentar.', 'error');
        await invalidateCase(queryClient, code);
        onClose();
        return;
      }
      const apiErr = toApiError(err);
      if (apiErr.fields && Object.keys(apiErr.fields).length > 0) {
        setErrors(apiErr.fields);
      } else {
        setFormError(err);
      }
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validateValues(action.form, values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setFormError(null);
    mutation.mutate({
      ...buildPayload(action.form, values),
      expected_version: version,
      idempotency_key: idempotencyKey,
    });
  }

  return (
    <Modal
      title={action.label}
      onClose={() => {
        if (!mutation.isPending) onClose();
      }}
      footer={
        <>
          <button type="button" className="btn secondary" onClick={onClose} disabled={mutation.isPending}>Cancelar</button>
          <button type="submit" form={`action-form-${action.name}`} className={`btn${action.danger ? ' danger' : ''}`} disabled={mutation.isPending}>
            {mutation.isPending ? 'Registrando…' : action.label}
          </button>
        </>
      }
    >
      <p className="muted">{action.description}</p>
      {formError != null && <ErrorNotice error={formError} />}
      {action.form.length === 0 && <Notice tone="blue">Esta acción se registra en la auditoría con tu usuario y rol.</Notice>}
      <DynamicForm
        id={`action-form-${action.name}`}
        fields={action.form}
        values={values}
        onChange={setValues}
        errors={errors}
        documents={documents}
        onSubmit={submit}
      />
    </Modal>
  );
}
