import { useState } from "react";
import { createNote, getSuggestions, decideSuggestion, Suggestion } from "./api";

const CLINICIAN_ID = "gp1";

export default function App() {
  const [patientRef, setPatientRef] = useState("");
  const [noteText, setNoteText] = useState("");
  const [noteId, setNoteId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCode, setEditCode] = useState("");

  async function submitNote() {
    const note = await createNote(patientRef, CLINICIAN_ID, noteText);
    setNoteId(note.id);
    setSuggestions(await getSuggestions(note.id));
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
    <div style={{ maxWidth: 640, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>ClinCode</h1>
      <p>Free-text consultation note → suggested SNOMED CT codes for review.</p>

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
        rows={6}
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
            <strong>{s.term}</strong> ({s.snomed_code}) — confidence {s.confidence.toFixed(2)} — status: {s.status}
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
  );
}
