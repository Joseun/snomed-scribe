import { useEffect, useState } from "react";
import { createNote, getSuggestions, decideSuggestion, previewExtraction, PreviewSuggestion, Suggestion } from "./api";

const CLINICIAN_ID = "gp1";
const PREVIEW_DEBOUNCE_MS = 900;
const PREVIEW_MIN_LENGTH = 20;

export default function App() {
  const [patientRef, setPatientRef] = useState("");
  const [noteText, setNoteText] = useState("");
  const [noteId, setNoteId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCode, setEditCode] = useState("");
  const [livePreview, setLivePreview] = useState<PreviewSuggestion[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (noteText.trim().length < PREVIEW_MIN_LENGTH) {
      setLivePreview([]);
      setPreviewLoading(false);
      return;
    }

    const controller = new AbortController();
    setPreviewLoading(true);
    const timer = setTimeout(() => {
      previewExtraction(noteText, controller.signal)
        .then((result) => {
          setLivePreview(result);
          setPreviewLoading(false);
        })
        .catch((err) => {
          if (err.name !== "AbortError") setPreviewLoading(false);
        });
    }, PREVIEW_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [noteText]);

  async function submitNote() {
    const note = await createNote(patientRef, CLINICIAN_ID, noteText);
    setNoteId(note.id);
    setSuggestions(await getSuggestions(note.id));
    setLivePreview([]);
  }

  async function decide(id: string, action: "accept" | "reject") {
    await decideSuggestion(id, action, CLINICIAN_ID);
    if (noteId) setSuggestions(await getSuggestions(noteId));
  }

  function startEdit(id: string, currentCode: string) {
    setEditingId(id);
    setEditCode(currentCode);
  }

  async function submitEdit(id: string) {
    if (!editCode.trim()) return;
    await decideSuggestion(id, "edit", CLINICIAN_ID, editCode.trim());
    setEditingId(null);
    setEditCode("");
    if (noteId) setSuggestions(await getSuggestions(noteId));
  }

  return (
    <div style={{ maxWidth: 1000, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>ClinCode</h1>
      <p>Free-text consultation note → suggested SNOMED CT codes for review.</p>

      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        <div style={{ flex: "1 1 60%", minWidth: 0 }}>
          <input
            placeholder="Patient reference"
            value={patientRef}
            onChange={(e) => setPatientRef(e.target.value)}
            style={{ width: "100%", marginBottom: 8 }}
          />
          <textarea
            placeholder="Type the consultation note..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={10}
            style={{ width: "100%", marginBottom: 8 }}
          />
          <button onClick={submitNote} disabled={!patientRef || !noteText}>
            Extract codes
          </button>

          <h2>Suggestions</h2>
          {suggestions.length === 0 && <p>No suggestions yet.</p>}
          <ul>
            {suggestions.map((s) => (
              <li key={s.id} style={{ marginBottom: 8 }}>
                <strong>{s.term}</strong> ({s.snomed_code}) — confidence {s.confidence.toFixed(2)} — status:{" "}
                {s.status}
                {s.status === "pending" && editingId !== s.id && (
                  <>
                    <button onClick={() => decide(s.id, "accept")} style={{ marginLeft: 8 }}>
                      Accept
                    </button>
                    <button onClick={() => startEdit(s.id, s.snomed_code)} style={{ marginLeft: 4 }}>
                      Edit
                    </button>
                    <button onClick={() => decide(s.id, "reject")} style={{ marginLeft: 4 }}>
                      Reject
                    </button>
                  </>
                )}
                {editingId === s.id && (
                  <div style={{ marginTop: 4 }}>
                    <input
                      placeholder="Replacement SNOMED code"
                      value={editCode}
                      onChange={(e) => setEditCode(e.target.value)}
                      style={{ marginRight: 4 }}
                    />
                    <button onClick={() => submitEdit(s.id)}>Save</button>
                    <button onClick={() => setEditingId(null)} style={{ marginLeft: 4 }}>
                      Cancel
                    </button>
                  </div>
                )}
                {s.status === "edited" && s.resolved_code && (
                  <span style={{ marginLeft: 8 }}>→ resolved: {s.resolved_code}</span>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div
          style={{
            flex: "1 1 40%",
            minWidth: 0,
            border: "1px solid #ddd",
            borderRadius: 6,
            padding: 12,
            position: "sticky",
            top: 16,
          }}
        >
          <h2 style={{ marginTop: 0 }}>Live scan {previewLoading && <span style={{ fontSize: 12 }}>…</span>}</h2>
          <p style={{ fontSize: 13, color: "#666" }}>
            Not persisted — review only. Codes aren't suggested on the patient record until you click "Extract
            codes" and accept them below.
          </p>
          {noteText.trim().length < PREVIEW_MIN_LENGTH && <p>Keep typing to see live suggestions…</p>}
          {noteText.trim().length >= PREVIEW_MIN_LENGTH && livePreview.length === 0 && !previewLoading && (
            <p>No candidates found yet.</p>
          )}
          <ul style={{ paddingLeft: 18 }}>
            {livePreview.map((p, i) => (
              <li key={`${p.snomed_code}-${i}`} style={{ marginBottom: 6 }}>
                <strong>{p.term}</strong> ({p.snomed_code}) — {Math.round(p.confidence * 100)}%
                <br />
                <span style={{ fontSize: 12, color: "#888" }}>"{p.source_span}"</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
