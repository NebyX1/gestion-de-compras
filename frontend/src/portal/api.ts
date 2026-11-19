import { useQuery } from '@tanstack/react-query';
import { api, request, setCsrfToken } from '../api/client';
import { authApi } from '../api/endpoints';
import type { Paged } from '../api/types';

export type PublicStatus = 'open' | 'closed' | 'awarded';

export interface TenderSummary {
  code: string;
  title: string;
  area: string;
  procedure_type: string;
  procedure_label: string;
  status: PublicStatus;
  status_label: string;
  published_at: string;
  deadline: string | null;
  currency: string;
  can_submit: boolean;
  is_demo: boolean;
}

export interface TenderLine {
  id: number;
  position: number;
  description: string;
  quantity: string;
  unit: string;
}

export interface Award {
  supplier: string;
  amount: string;
  freight?: string;
  discount?: string;
  currency: string;
  reference: string;
  awarded_at: string;
  published_at: string;
  grounds: string;
  departure_reason: string | null;
  recommended_supplier: string | null;
  recommendation_reason: string | null;
  followed_recommendation: boolean | null;
  ai_explanation: string | null;
  ai_model: string | null;
  ai_recommended_supplier?: string | null;
  followed_ai_recommendation?: boolean | null;
  ai_abstained?: boolean;
  evaluation_version: number | null;
  lines: { description: string; quantity: string; unit: string; unit_price: string; tax_rate: string; amount: string }[];
}

export interface Tender extends TenderSummary {
  need_text: string;
  delivery_place: string | null;
  lines: TenderLine[];
  spec: {
    id: number;
    version: number;
    minimum_text: string | null;
    delivery_terms: string | null;
    reception_channel: string;
    reception_place: string | null;
    mode: string;
    attachment?: { filename: string; url: string; size: number; version: number } | null;
    requirements: { code: string; text: string; essential: boolean; kind: string; attribute: string | null; operator: string | null; threshold: string | null; unit: string | null }[];
    criteria: { name: string; weight: string; description: string | null; type: string; attribute: string | null; scale: { min: string; max: string | null; points: string }[] }[];
  };
  award: Award | null;
}

export interface Contact {
  supplier_name: string;
  tax_id: string;
  email: string;
}

export interface OfferPayload extends Contact {
  verification_code: string;
  spec_id: number;
  lines: { request_line_id: number; unit_price: string; tax_rate: string }[];
  prices_include_tax: boolean;
  freight: string;
  delivery_days: number;
  warranty_months: number;
  technical_description: string;
  accepted_terms: boolean;
}

export interface OfferReceipt {
  receipt_code: string;
  received_at: string;
  tender_code: string;
}

const resource = (code: string) => `/public/tenders/${encodeURIComponent(code)}`;
export const tenderPath = (code: string) => `/licitaciones/${encodeURIComponent(code)}`;

export function useTenders(q: string, status: PublicStatus | '', page: number) {
  return useQuery({
    queryKey: ['public-tenders', q, status, page],
    queryFn: ({ signal }) => request(api.get<Paged<TenderSummary>>('/public/tenders', {
      params: { q: q || undefined, status: status || undefined, page, per_page: 9 }, signal,
    })),
  });
}

export function useTender(code: string) {
  return useQuery({
    queryKey: ['public-tender', code],
    queryFn: ({ signal }) => request(api.get<Tender>(resource(code), { signal })),
  });
}

async function preparePublicWrite() {
  const session = await authApi.challenge();
  setCsrfToken(session.csrf_token);
}

export async function sendCode(code: string, contact: Contact) {
  await preparePublicWrite();
  return request(api.post<{ message: string }>(`${resource(code)}/verification`, {
    tax_id: contact.tax_id.trim(), email: contact.email.trim(),
  }));
}

export async function submitOffer(code: string, payload: OfferPayload, idempotencyKey: string, file: File | null) {
  await preparePublicWrite();
  const form = new FormData();
  if (file) {
    form.append('offer', JSON.stringify(payload));
    form.append('file', file);
  }
  return request(api.post<OfferReceipt>(`${resource(code)}/offers`, file ? form : payload, {
    headers: { 'Idempotency-Key': idempotencyKey },
  }));
}
