from app.extraction import SnomedConcept, extract_candidates

SUBSET = [
    SnomedConcept(code="29857009", term="Chest pain", synonyms=()),
    SnomedConcept(code="267036007", term="Dyspnea", synonyms=("shortness of breath", "SOB")),
]


class StubClient:
    def __init__(self, raw_candidates):
        self.raw_candidates = raw_candidates

    def complete(self, note_text, concepts):
        return self.raw_candidates


def test_valid_candidate_is_kept():
    note = "Patient reports chest pain for two days."
    client = StubClient(
        [{"term": "Chest pain", "snomed_code": "29857009", "confidence": 0.9, "source_span": "chest pain"}]
    )
    results = extract_candidates(note, client, SUBSET)
    assert len(results) == 1
    assert results[0].snomed_code == "29857009"


def test_negated_candidate_is_dropped():
    note = "Patient denies chest pain but reports SOB on exertion."
    client = StubClient(
        [
            {"term": "Chest pain", "snomed_code": "29857009", "confidence": 0.8, "source_span": "chest pain"},
            {"term": "Dyspnea", "snomed_code": "267036007", "confidence": 0.85, "source_span": "SOB"},
        ]
    )
    results = extract_candidates(note, client, SUBSET)
    codes = {c.snomed_code for c in results}
    assert "29857009" not in codes
    assert "267036007" in codes


def test_out_of_subset_code_is_rejected():
    note = "Patient has a headache."
    client = StubClient(
        [{"term": "Headache", "snomed_code": "25064002", "confidence": 0.7, "source_span": "headache"}]
    )
    results = extract_candidates(note, client, SUBSET)
    assert results == []
