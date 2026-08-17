"""Tests for LLM-powered false positive filter.

Uses unittest.mock to patch the LLM client, avoiding network calls in CI.
"""

from unittest.mock import MagicMock, patch

import spacy


class TestFilterFalsePositives:
    """Tests for the filter_false_positives function."""

    def setup_method(self):
        """Load spaCy model for each test."""
        self.nlp = spacy.load("en_core_web_sm")

    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_returns_issues_unchanged_without_llm(self, mock_get_client):
        """filter_false_positives returns issues unchanged when LLM is not configured."""
        mock_get_client.return_value = None

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The running gear drives the shaft.")
        issues = [
            {"type": "VerbForms", "message": "test", "offset": 4, "length": 7},
            {"type": "MissingArticles", "message": "test2", "offset": 20, "length": 5},
        ]
        result = filter_false_positives(issues, doc)
        assert len(result) == 2

    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_non_filterable_checks_pass_through(self, mock_get_client):
        """Non-filterable checks pass through unchanged."""
        mock_get_client.return_value = MagicMock()

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The test.")
        issues = [
            {"type": "MissingArticles", "message": "test", "offset": 4, "length": 5},
            {"type": "VerbTenses", "message": "test2", "offset": 0, "length": 3},
        ]
        result = filter_false_positives(issues, doc)
        assert len(result) == 2

    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_skip_llm_for_single_issue(self, mock_get_client):
        """LLM is not called when fewer than 2 filterable issues exist."""
        mock_get_client.return_value = MagicMock()

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The test.")
        issues = [
            {"type": "VerbForms", "message": "single issue", "offset": 4, "length": 7},
        ]
        result = filter_false_positives(issues, doc)
        # Single issue: no LLM call, kept as-is.
        assert len(result) == 1

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_verbfoms_false_positive_suppressed(self, mock_get_client, mock_chat):
        """VerbForms false positive (running in 'running gear') is suppressed."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "Issue 1 [VerbForms]: FALSE_POSITIVE\nIssue 2 [VerbForms]: FALSE_POSITIVE"

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The running gear drives the main shaft. The cooling water flows.")
        issues = [
            {"type": "VerbForms", "message": "Do not use 'running' (VBG).", "offset": 4, "length": 7},
            {"type": "VerbForms", "message": "Do not use 'cooling' (VBG).", "offset": 45, "length": 7},
        ]
        result = filter_false_positives(issues, doc)
        verbfoms = [i for i in result if i["type"] == "VerbForms"]
        assert len(verbfoms) == 0

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_verbfoms_genuine_confirmed(self, mock_get_client, mock_chat):
        """VerbForms genuine issue (is running) is confirmed."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "Issue 1 [VerbForms]: CONFIRM"

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The pump is running.")
        issues = [
            {"type": "VerbForms", "message": "Do not use 'running' (VBG).", "offset": 11, "length": 7},
        ]
        result = filter_false_positives(issues, doc)
        verbfoms = [i for i in result if i["type"] == "VerbForms"]
        assert len(verbfoms) == 1

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_connecting_words_rule_prefilter(self, mock_get_client, mock_chat):
        """ConnectingWords with unrelated sentences is pre-filtered (no LLM call)."""
        mock_get_client.return_value = MagicMock()

        from stelint.checks_llm_fp import filter_false_positives

        # Two sentences with no shared content words.
        doc = self.nlp("The pump runs at full speed. The bearing temperature is high.")
        issues = [
            {
                "type": "ConnectingWords",
                "message": "Consider adding a connecting word.",
                "offset": 30,
                "length": 0,
            },
        ]
        # Only 1 filterable issue, below threshold → no LLM call.
        result = filter_false_positives(issues, doc)
        assert len(result) == 1

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_connecting_words_false_positive_suppressed(self, mock_get_client, mock_chat):
        """ConnectingWords false positive (unrelated topics) is suppressed."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "Issue 1 [ConnectingWords]: FALSE_POSITIVE"

        from stelint.checks_llm_fp import filter_false_positives

        # Two sentences with some shared words (won't trigger pre-filter).
        doc = self.nlp("The pump runs at full speed. The pump temperature is high.")
        issues = [
            {
                "type": "ConnectingWords",
                "message": "Consider adding a connecting word.",
                "offset": 30,
                "length": 0,
            },
            {
                "type": "ConnectingWords",
                "message": "Consider adding a connecting word.",
                "offset": 60,
                "length": 0,
            },
        ]
        result = filter_false_positives(issues, doc)
        connecting = [i for i in result if i["type"] == "ConnectingWords"]
        assert len(connecting) == 0

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_part_of_speech_false_positive_suppressed(self, mock_get_client, mock_chat):
        """PartOfSpeech false positive (correct verb usage) is suppressed."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "Issue 1 [PartOfSpeech]: FALSE_POSITIVE\nIssue 2 [VerbForms]: CONFIRM"

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The operator runs the pump at rated speed. The pump is running.")
        issues = [
            {
                "type": "PartOfSpeech",
                "message": "Word 'run' is used as VERB but should be used as NOUN.",
                "offset": 18,
                "length": 3,
            },
            {
                "type": "VerbForms",
                "message": "Do not use 'running' (VBG).",
                "offset": 45,
                "length": 7,
            },
        ]
        result = filter_false_positives(issues, doc)
        pos_issues = [i for i in result if i["type"] == "PartOfSpeech"]
        assert len(pos_issues) == 0

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_technical_verb_as_noun_false_positive_suppressed(self, mock_get_client, mock_chat):
        """TechnicalVerbAsNoun false positive (noun modifier) is suppressed."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "Issue 1 [TechnicalVerbAsNoun]: FALSE_POSITIVE\nIssue 2 [VerbForms]: CONFIRM"

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The test results show improvement. The pump is running.")
        issues = [
            {
                "type": "TechnicalVerbAsNoun",
                "message": "Do not use technical verb 'test' as a noun.",
                "offset": 4,
                "length": 4,
            },
            {
                "type": "VerbForms",
                "message": "Do not use 'running' (VBG).",
                "offset": 40,
                "length": 7,
            },
        ]
        result = filter_false_positives(issues, doc)
        tvn = [i for i in result if i["type"] == "TechnicalVerbAsNoun"]
        assert len(tvn) == 0

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_graceful_on_llm_failure(self, mock_get_client, mock_chat):
        """All issues kept when LLM call fails (conservative fallback)."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = None  # LLM returned nothing

        from stelint.checks_llm_fp import filter_false_positives

        # Use issues that bypass pre-filters: genuine progressive verbs
        # (after be-verb) and unrelated ConnectingWords (no LLM call needed
        # for single issue, so use 2 genuine VerbForms + 1 ConnectingWords).
        doc = self.nlp("The pump is running. The valve is opening. The pump pressure is high. The pump flow is low.")
        issues = [
            {"type": "VerbForms", "message": "test", "offset": 11, "length": 7},
            {"type": "VerbForms", "message": "test2", "offset": 33, "length": 7},
            {"type": "ConnectingWords", "message": "test3", "offset": 60, "length": 0},
        ]
        result = filter_false_positives(issues, doc)
        # All 3 kept on failure (conservative fallback).
        assert len(result) == 3

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_mixed_confirm_and_suppress(self, mock_get_client, mock_chat):
        """Some issues confirmed, others suppressed in same batch."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "1: FALSE_POSITIVE\n2: CONFIRM"

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The running gear drives the shaft. The pump is running.")
        issues = [
            {"type": "VerbForms", "message": "running in gear", "offset": 4, "length": 7},
            {"type": "VerbForms", "message": "actual issue", "offset": 47, "length": 7},
        ]
        result = filter_false_positives(issues, doc)
        # Only the CONFIRMed issue remains.
        assert len(result) == 1
        assert "actual issue" in result[0]["message"]

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_empty_issues_list(self, mock_get_client, mock_chat):
        """Empty issues list returns empty."""
        mock_get_client.return_value = MagicMock()

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The test.")
        result = filter_false_positives([], doc)
        assert result == []

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_single_llm_call_for_all_types(self, mock_get_client, mock_chat):
        """Pre-filters handle obvious cases; LLM only for ambiguous ones."""
        mock_get_client.return_value = MagicMock()

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("The pump is running. The valve is opening. The running gear drives the shaft. The pressure is high and the flow is low. The operator checks the gauge.")
        issues = [
            # Genuine VerbForms (after be-verb) → pre_confirmed.
            {"type": "VerbForms", "message": "test", "offset": 12, "length": 7},
            # ConnectingWords with unrelated sentences → pre-suppressed.
            {"type": "ConnectingWords", "message": "test2", "offset": 42, "length": 0},
            # PartOfSpeech with clear verb deps → pre_confirmed.
            {"type": "PartOfSpeech", "message": "test3", "offset": 133, "length": 7},
        ]
        result = filter_false_positives(issues, doc)
        # Pre-filters handle everything → no LLM call needed.
        assert mock_chat.call_count == 0
        # VerbForms and PartOfSpeech kept, ConnectingWords suppressed.
        assert len(result) == 2
        types = {r["type"] for r in result}
        assert "VerbForms" in types
        assert "PartOfSpeech" in types

    @patch("stelint.checks_llm_fp.llm_chat")
    @patch("stelint.checks_llm_fp.get_llm_client")
    def test_truncation_keeps_excess_issues(self, mock_get_client, mock_chat):
        """Issues beyond max are kept (conservative truncation)."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = ""

        from stelint.checks_llm_fp import filter_false_positives

        doc = self.nlp("x" * 1000)
        # Create 25 VerbForms issues (exceeds _MAX_TOTAL_ISSUES=20).
        issues = [{"type": "VerbForms", "message": f"issue {i}", "offset": i * 10, "length": 5} for i in range(25)]
        result = filter_false_positives(issues, doc)
        # LLM processes first 20, keeps all 5 beyond truncation.
        assert len(result) == 25
