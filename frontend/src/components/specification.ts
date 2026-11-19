import type { FormField } from '../api/types';

function field(name: string, label: string, type = 'text', settings: Partial<FormField> = {}): FormField {
  return { name, label, type, required: true, ...settings };
}
function options(pairs: [string, string][]) {
  return pairs.map(([value, label]) => ({ value, label }));
}
const attributes = options([['delivery_days', 'Plazo de entrega (días)'], ['warranty_months', 'Garantía (meses)']]);
const numeric = { when: { key: 'kind', value: 'numeric' } };
const scale = { when: { key: 'type', value: 'scale' } };

export const specificationFields = [
  field('minimum_text', 'Descripción pública y condiciones mínimas', 'textarea'),
  field('reception_channel', 'Canal de recepción', 'select', { default: 'portal', options: options([
    ['portal', 'Portal público de Lavalleja'], ['presencial', 'Presencial'], ['electronico_arce', 'Electrónico ARCE'],
    ['correo_pliego', 'Correo indicado en el pliego'], ['otro', 'Otro canal'],
  ]) }),
  field('offer_deadline', 'Cierre de ofertas (hora de Uruguay)', 'datetime', { required: false }),
  field('reception_place', 'Lugar de recepción', 'text', { required: false }),
  field('delivery_terms', 'Condición de entrega', 'text', { required: false }),
  field('requirements', 'Requisitos del pliego', 'lines', { itemLabel: 'requisito', fields: [
    field('code', 'Código', 'text', { required: false }), field('text', 'Requisito'),
    field('essential', 'Excluyente', 'checkbox', { required: false, default: true }),
    field('kind', 'Verificación', 'select', { default: 'review', options: options([['review', 'Revisión técnica'], ['numeric', 'Comparación numérica']]) }),
    field('attribute', 'Dato a comparar', 'select', { ...numeric, options: attributes }),
    field('operator', 'Comparación', 'select', { ...numeric, options: options([['gte', 'Al menos'], ['lte', 'Hasta'], ['gt', 'Mayor que'], ['lt', 'Menor que'], ['eq', 'Igual a']]) }),
    field('threshold', 'Umbral', 'number', numeric), field('unit', 'Unidad', 'text', { required: false }),
  ] }),
  field('mode', 'Método de evaluación', 'select', { default: 'min_price', options: options([
    ['min_price', 'Menor precio admisible'], ['weighted', 'Factores ponderados'], ['framework', 'Convenio marco'],
  ]) }),
  field('currency', 'Moneda de evaluación', 'text', { default: 'UYU' }),
  field('criteria', 'Criterios ponderados', 'lines', { when: { key: 'mode', value: 'weighted' }, itemLabel: 'criterio',
    help: 'Distribuí 100 puntos entre los criterios.', fields: [
      field('code', 'Código', 'text', { required: false }), field('name', 'Nombre del criterio'),
      field('weight', 'Puntos máximos', 'number', { min: 0.0001, max: 100 }),
      field('type', 'Forma de puntuar', 'select', { default: 'price_ratio', options: options([['price_ratio', 'Precio proporcional'], ['scale', 'Escala por tramos'], ['manual', 'Revisión cualitativa']]) }),
      field('description', 'Descripción del criterio', 'textarea', { required: false }),
      field('attribute', 'Dato de la escala', 'select', { ...scale, options: attributes }),
      field('scale', 'Tramos de la escala', 'lines', { ...scale, itemLabel: 'tramo', fields: [
        field('min', 'Desde', 'number', { required: false }), field('max', 'Hasta', 'number', { required: false }), field('points', 'Puntos', 'number', { min: 0 }),
      ] }),
    ] }),
];

export function initialSpecification(raw: unknown): Record<string, unknown> {
  const spec = (raw ?? {}) as Record<string, unknown>;
  let deadline = '';
  if (typeof spec.offer_deadline === 'string' && spec.offer_deadline) {
    const date = new Date(spec.offer_deadline);
    if (!Number.isNaN(date.getTime())) {
      const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Montevideo', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
      deadline = parts.format(date).replace(' ', 'T');
    }
  }
  return { ...spec, offer_deadline: deadline };
}
