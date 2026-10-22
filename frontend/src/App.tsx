import { useState } from "react";
import { createNote, getSuggestions, decideSuggestion, Suggestion } from "./api";

const CLINICIAN_ID = "gp1";

export default function App() {
  const [patientRef, setPatientRef] = useState("");
  const [noteText, setNoteText] = useState("");
  const [noteId, setNoteId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  async function submitNote() {
    const note = await createNote(patientRef, CLINICIAN_ID, noteText);
    setNoteId(note.id);
    setSuggestions(await getSuggestions(note.id));
  }

  async function decide(id: string, action: "accept" | "reject") {
    await decideSuggestion(id, action, CLINICIAN_ID);
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
            {s.status === "pending" && (
              <>
                <button onClick={() => decide(s.id, "accept")} style={{ marginLeft: 8 }}>
                  Accept
                </button>
                <button onClick={() => decide(s.id, "reject")} style={{ marginLeft: 4 }}>
                  Reject
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
