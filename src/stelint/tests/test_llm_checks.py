"""Tests for LLM-powered stelint checks.

Uses unittest.mock to patch the LLM client, avoiding network calls in CI.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import spacy


class TestLLMClient:
    """Tests for the llm_client module."""

    def test_returns_none_without_env_var(self):
        """get_llm_client returns None when STELINT_LLM_BASE_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure the env var is removed if present.
            os.environ.pop("STELINT_LLM_BASE_URL", None)
            from stelint.llm_client import get_llm_client

            # Force reset of cached client.
            stelint.llm_client._client = None
            assert get_llm_client() is None

    def test_returns_client_with_env_var(self):
        """get_llm_client returns an OpenAI client when env vars are set."""
        with patch.dict(os.environ, {"STELINT_LLM_BASE_URL": "http://test:9999/v1"}):
            mock_openai = MagicMock()
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client
            mock_client.models.list.return_value = MagicMock()

            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint import llm_client

                llm_client._client = None
                client = llm_client.get_llm_client()
                assert client is not None
                mock_openai.OpenAI.assert_called_once()

    def test_llm_chat_returns_none_without_client(self):
        """llm_chat returns None when no client is available."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STELINT_LLM_BASE_URL", None)
            from stelint.llm_client import llm_chat

            stelint.llm_client._client = None
            assert llm_chat([{"role": "user", "content": "hi"}]) is None


class TestCheckLLMPolysemy:
    """Tests for the check_llm_polysemy function."""

    def setup_method(self):
        """Load spaCy model for each test."""
        self.nlp = spacy.load("en_core_web_sm")

    @patch("stelint.checks_llm.llm_chat")
    @patch("stelint.checks_llm.get_llm_client")
    def test_returns_empty_when_no_llm(self, mock_get_client, mock_chat):
        """check_llm_polysemy returns [] when LLM is not configured."""
        mock_get_client.return_value = None
        doc = self.nlp("This is a test with some words.")
        result = __import__("stelint.checks_llm", fromlist=["check_llm_polysemy"]).check_llm_polysemy(doc)
        assert result == []

    @patch("stelint.checks_llm.llm_chat")
    @patch("stelint.checks_llm.get_llm_client")
    def test_no_issue_for_same_meaning(self, mock_get_client, mock_chat):
        """No issue when LLM says the word has the same meaning."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "SAME"

        from stelint.checks_llm import check_llm_polysemy

        doc = self.nlp("Run the test script. Run the maintenance procedure. Run the department protocol.")
        result = check_llm_polysemy(doc)
        # 'run' appears 3 times but LLM says SAME, so no issue.
        polysemous = [i for i in result if i["type"] == "LLMPolysemy"]
        assert len(polysemous) == 0

    @patch("stelint.checks_llm.llm_chat")
    @patch("stelint.checks_llm.get_llm_client")
    def test_issue_for_different_meaning(self, mock_get_client, mock_chat):
        """Issue when LLM says the word has different meanings."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "'run': DIFFERENT: execute vs manage"

        from stelint.checks_llm import check_llm_polysemy

        doc = self.nlp("Run the test script. Run the maintenance procedure. Run the department.")
        result = check_llm_polysemy(doc)
        polysemous = [i for i in result if i["type"] == "LLMPolysemy"]
        assert len(polysemous) == 1
        assert "run" in polysemous[0]["message"].lower()
        assert polysemous[0]["offset"] == doc[0].idx

    @patch("stelint.checks_llm.llm_chat")
    @patch("stelint.checks_llm.get_llm_client")
    def test_skips_words_with_different_pos(self, mock_get_client, mock_chat):
        """Words with different POS tags are skipped (spaCy handles them)."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "DIFFERENT: noun vs adjective"

        from stelint.checks_llm import check_llm_polysemy

        # 'light' as NOUN and ADJ — different POS, so skipped by LLM check.
        doc = self.nlp("Turn on the light. The package is light.")
        result = check_llm_polysemy(doc)
        polysemous = [i for i in result if i["type"] == "LLMPolysemy"]
        assert len(polysemous) == 0

    @patch("stelint.checks_llm.llm_chat")
    @patch("stelint.checks_llm.get_llm_client")
    def test_skips_rare_words(self, mock_get_client, mock_chat):
        """Words appearing fewer than 3 times are skipped."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = "DIFFERENT: meaning a vs meaning b"

        from stelint.checks_llm import check_llm_polysemy

        doc = self.nlp("The container holds data. The container stores files.")
        # 'container' appears only 2 times, below threshold.
        result = check_llm_polysemy(doc)
        polysemous = [i for i in result if i["type"] == "LLMPolysemy"]
        assert len(polysemous) == 0

    @patch("stelint.checks_llm.llm_chat")
    @patch("stelint.checks_llm.get_llm_client")
    def test_graceful_on_llm_failure(self, mock_get_client, mock_chat):
        """check_llm_polysemy returns [] when LLM call fails."""
        mock_get_client.return_value = MagicMock()
        mock_chat.return_value = None  # LLM returned nothing

        from stelint.checks_llm import check_llm_polysemy

        doc = self.nlp("Run the test script. Run the maintenance procedure. Run the department.")
        result = check_llm_polysemy(doc)
        polysemous = [i for i in result if i["type"] == "LLMPolysemy"]
        assert len(polysemous) == 0

    @patch("stelint.checks_llm.llm_chat")
    @patch("stelint.checks_llm.get_llm_client")
    def test_skips_proper_nouns(self, mock_get_client, mock_chat):
        """Proper nouns are skipped (they are names, not polysemous)."""
        mock_get_client.return_value = MagicMock()

        from stelint.checks_llm import check_llm_polysemy

        doc = self.nlp("The Python library is useful. Python is a programming language.")
        result = check_llm_polysemy(doc)
        # 'Python' is PROPN in both cases, should be skipped.
        polysemous = [i for i in result if i["type"] == "LLMPolysemy"]
        assert len(polysemous) == 0


# Import the llm_client module at module level for test references.
import stelint.llm_client
