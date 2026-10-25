const BASE = "/api";

export interface Suggestion {
  id: string;
  note_id: string;
  snomed_code: string;
  term: string;
  confidence: number;
  source_span: string | null;
  status: string;
  resolved_code: string | null;
}

export async function createNote(patientRef: string, clinicianId: string, rawText: string) {
  const res = await fetch(`${BASE}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_ref: patientRef, clinician_id: clinicianId, raw_text: rawText }),
  });
  return res.json();
}

export async function getSuggestions(noteId: string): Promise<Suggestion[]> {
  const res = await fetch(`${BASE}/notes/${noteId}/suggestions`);
  return res.json();
}

export interface PreviewSuggestion {
  snomed_code: string | null;
  term: string;
  confidence: number;
  source_span: string;
}

export async function previewExtraction(rawText: string, signal?: AbortSignal): Promise<PreviewSuggestion[]> {
  const res = await fetch(`${BASE}/notes/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText }),
    signal,
  });
  return res.json();
}

export async function decideSuggestion(
  suggestionId: string,
  action: "accept" | "edit" | "reject",
  decidedBy: string,
  resolvedCode?: string
) {
  const res = await fetch(`${BASE}/suggestions/${suggestionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, decided_by: decidedBy, resolved_code: resolvedCode }),
  });
  return res.json();
}
