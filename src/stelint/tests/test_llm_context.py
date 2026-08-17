"""Tests for LLM-powered context classification."""

import os
import sys
from unittest.mock import MagicMock, patch

# Add the src directory to the path so we can import stelint modules.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestClassifySentences:
    """Test sentence classification."""

    def setup_method(self):
        """Set up test fixtures."""
        import spacy

        self.nlp = spacy.load("en_core_web_sm")

    @patch("stelint.checks_llm_context.llm_chat")
    @patch("stelint.checks_llm_context.get_llm_client")
    def test_returns_empty_dict_without_llm(self, mock_get_client, mock_chat):
        """Without LLM, returns empty dict (no-op behavior)."""
        mock_get_client.return_value = None
        mock_chat.return_value = "1:PROCEDURAL 2:DESCRIPTIVE"

        from stelint.checks_llm_context import classify_sentences

        doc = self.nlp("Remove the cap. The cap is made of rubber.")
        result = classify_sentences(doc)
        assert result == {}

    @patch("stelint.checks_llm_context.llm_chat")
    @patch("stelint.checks_llm_context.get_llm_client")
    def test_classifies_procedural_sentences(self, mock_get_client, mock_chat):
        """LLM correctly classifies procedural sentences."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "1:PROCEDURAL 2:PROCEDURAL 3:PROCEDURAL"

        from stelint.checks_llm_context import classify_sentences

        doc = self.nlp("Remove the cap. Install the bolt. Check the pressure.")
        result = classify_sentences(doc)
        assert result == {0: "PROCEDURAL", 1: "PROCEDURAL", 2: "PROCEDURAL"}

    @patch("stelint.checks_llm_context.llm_chat")
    @patch("stelint.checks_llm_context.get_llm_client")
    def test_classifies_descriptive_sentences(self, mock_get_client, mock_chat):
        """LLM correctly classifies descriptive sentences."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "1:DESCRIPTIVE 2:DESCRIPTIVE"

        from stelint.checks_llm_context import classify_sentences

        doc = self.nlp("The cap is made of rubber. Water flows through the valve.")
        result = classify_sentences(doc)
        assert result == {0: "DESCRIPTIVE", 1: "DESCRIPTIVE"}

    @patch("stelint.checks_llm_context.llm_chat")
    @patch("stelint.checks_llm_context.get_llm_client")
    def test_classifies_mixed_contexts(self, mock_get_client, mock_chat):
        """LLM correctly classifies mixed procedural/descriptive/safety."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "1:PROCEDURAL 2:DESCRIPTIVE 3:SAFETY 4:PROCEDURAL 5:DESCRIPTIVE"

        from stelint.checks_llm_context import classify_sentences

        doc = self.nlp("Remove the cap. The cap is made of rubber. Caution: Hot surface. Install the bolt. Water flows through the valve.")
        result = classify_sentences(doc)
        assert result == {
            0: "PROCEDURAL",
            1: "DESCRIPTIVE",
            2: "SAFETY",
            3: "PROCEDURAL",
            4: "DESCRIPTIVE",
        }

    @patch("stelint.checks_llm_context.llm_chat")
    @patch("stelint.checks_llm_context.get_llm_client")
    def test_handles_empty_document(self, mock_get_client, mock_chat):
        """Empty document returns empty dict."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = ""

        from stelint.checks_llm_context import classify_sentences

        doc = self.nlp("")
        result = classify_sentences(doc)
        assert result == {}

    @patch("stelint.checks_llm_context.llm_chat")
    @patch("stelint.checks_llm_context.get_llm_client")
    def test_handles_llm_failure(self, mock_get_client, mock_chat):
        """LLM failure returns empty dict (no-op behavior)."""
        mock_get_client.return_value = MagicMock()
        mock_chat.side_effect = Exception("Network error")

        from stelint.checks_llm_context import classify_sentences

        doc = self.nlp("Remove the cap.")
        result = classify_sentences(doc)
        assert result == {}

    @patch("stelint.checks_llm_context.llm_chat")
    @patch("stelint.checks_llm_context.get_llm_client")
    def test_handles_malformed_response(self, mock_get_client, mock_chat):
        """Malformed LLM response returns empty dict."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "this is not a valid response"

        from stelint.checks_llm_context import classify_sentences

        doc = self.nlp("Remove the cap.")
        result = classify_sentences(doc)
        assert result == {}


class TestApplyContextSuppressions:
    """Test context-based issue suppression."""

    def setup_method(self):
        """Set up test fixtures."""
        import spacy

        self.nlp = spacy.load("en_core_web_sm")

    def test_suppresses_imperative_in_description_for_procedural(self):
        """Procedural sentences suppress ImperativeInDescription."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("Remove the cap.")
        issues = [
            {
                "type": "ImperativeInDescription",
                "message": "test",
                "offset": 0,
                "length": 5,
            },
        ]
        sentence_types = {0: "PROCEDURAL"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        assert len(result) == 0

    def test_keeps_imperative_in_description_for_descriptive(self):
        """Descriptive sentences keep ImperativeInDescription."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("The cap is removed.")
        issues = [
            {
                "type": "ImperativeInDescription",
                "message": "test",
                "offset": 0,
                "length": 3,
            },
        ]
        sentence_types = {0: "DESCRIPTIVE"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        assert len(result) == 1

    def test_suppresses_non_imperative_in_procedures_for_descriptive(self):
        """Descriptive sentences suppress NonImperativeInProcedures."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("The cap is made of rubber.")
        issues = [
            {
                "type": "NonImperativeInProcedures",
                "message": "test",
                "offset": 0,
                "length": 3,
            },
        ]
        sentence_types = {0: "DESCRIPTIVE"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        assert len(result) == 0

    def test_suppresses_forbidden_modals_for_safety(self):
        """Safety sentences suppress ForbiddenModals."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("The system must operate at 100C.")
        issues = [
            {
                "type": "ForbiddenModals",
                "message": "test",
                "offset": 9,
                "length": 4,
            },
        ]
        sentence_types = {0: "SAFETY"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        assert len(result) == 0

    def test_keeps_forbidden_modals_for_procedural(self):
        """Procedural sentences keep ForbiddenModals."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("The pump must operate at 100C.")
        issues = [
            {
                "type": "ForbiddenModals",
                "message": "test",
                "offset": 9,
                "length": 4,
            },
        ]
        sentence_types = {0: "PROCEDURAL"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        assert len(result) == 1

    def test_suppresses_paragraph_checks_for_procedural(self):
        """Procedural sentences suppress paragraph structure checks."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("Check the oil level.")
        issues = [
            {
                "type": "ParagraphStructure",
                "message": "test",
                "offset": 0,
                "length": 10,
            },
        ]
        sentence_types = {0: "PROCEDURAL"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        assert len(result) == 0

    def test_no_suppression_without_context(self):
        """Without context, no issues are suppressed."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("Remove the cap.")
        issues = [
            {
                "type": "ImperativeInDescription",
                "message": "test",
                "offset": 0,
                "length": 5,
            },
        ]
        result = apply_context_suppressions(issues, {}, doc)
        assert len(result) == 1

    def test_no_suppression_for_unknown_sentence_type(self):
        """Unknown sentence types don't suppress anything."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("Remove the cap.")
        issues = [
            {
                "type": "ImperativeInDescription",
                "message": "test",
                "offset": 0,
                "length": 5,
            },
        ]
        sentence_types = {0: "UNKNOWN"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        assert len(result) == 1

    def test_suppresses_multiple_check_types(self):
        """Multiple check types are suppressed for the same sentence."""
        from stelint.checks_llm_context import apply_context_suppressions

        doc = self.nlp("Remove the cap. Install the bolt.")
        issues = [
            {
                "type": "ImperativeInDescription",
                "message": "test1",
                "offset": 0,
                "length": 5,
            },
            {
                "type": "ParagraphStructure",
                "message": "test2",
                "offset": 0,
                "length": 10,
            },
            {
                "type": "ForbiddenModals",
                "message": "test3",
                "offset": 0,
                "length": 4,
            },
        ]
        sentence_types = {0: "PROCEDURAL"}
        result = apply_context_suppressions(issues, sentence_types, doc)
        # ImperativeInDescription and ParagraphStructure suppressed, ForbiddenModals kept.
        assert len(result) == 1
        assert result[0]["type"] == "ForbiddenModals"
