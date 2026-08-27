"""Tests for deterministic heuristic context classification."""

from stelint.context_classifier import (
    apply_context_suppressions,
    classify_sentence_contexts,
)


class TestContextClassifier:
    """Tests for classify_sentence_contexts."""

    def test_empty_doc(self, nlp_model):
        doc = nlp_model("")
        res = classify_sentence_contexts(doc)
        assert res == {}

    def test_procedural_list_items(self, nlp_model):
        md = "# Procedure\n\n1. Remove the filter.\n2. Install the new pump.\n"
        doc = nlp_model(md)
        contexts = classify_sentence_contexts(doc, raw_text=md)
        assert len(contexts) > 0
        # Sentences under # Procedure with numbered steps should be classified as PROCEDURAL
        for idx, ctype in contexts.items():
            assert ctype in ("PROCEDURAL", "DESCRIPTIVE")

    def test_safety_context(self, nlp_model):
        md = "WARNING: Do not touch the cable."
        doc = nlp_model(md)
        contexts = classify_sentence_contexts(doc, raw_text=md)
        assert contexts.get(0) == "SAFETY"

    def test_descriptive_context(self, nlp_model):
        md = "# Description\n\nThe hydraulic system supplies fluid at high pressure to the actuators."
        doc = nlp_model(md)
        contexts = classify_sentence_contexts(doc, raw_text=md)
        # Should be classified as DESCRIPTIVE
        for idx, ctype in contexts.items():
            assert ctype == "DESCRIPTIVE"

    def test_apply_context_suppressions(self, nlp_model):
        doc = nlp_model("Remove the filter.")
        # Simulated issue on procedural sentence
        issues = [
            {"type": "ImperativeInDescription", "offset": 0, "length": 6},
            {"type": "ApprovedWords", "offset": 0, "length": 6},
        ]
        sentence_types = {0: "PROCEDURAL"}
        filtered = apply_context_suppressions(issues, sentence_types, doc)
        # ImperativeInDescription should be suppressed in PROCEDURAL context
        assert len(filtered) == 1
        assert filtered[0]["type"] == "ApprovedWords"
