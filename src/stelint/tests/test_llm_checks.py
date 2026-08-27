"""Tests for LLM-powered stelint checks.

Uses unittest.mock to patch the LLM client, avoiding network calls in CI.
"""

import os
import re
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

    def _mock_chat_client(self):
        """Build a mocked OpenAI client with a canned 'ok' response."""
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_client.models.list.return_value = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "ok"
        mock_message.reasoning_content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        return mock_openai, mock_client

    def test_llm_chat_no_extra_body_without_type(self):
        """llm_chat sends no extra_body when STELINT_LLM_TYPE is not set."""
        with patch.dict(os.environ, {"STELINT_LLM_BASE_URL": "http://test:9999/v1"}, clear=True):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint.llm_client import llm_chat

                stelint.llm_client._client = None
                result = llm_chat([{"role": "user", "content": "hi"}])
                assert result == "ok"
                _, kwargs = mock_client.chat.completions.create.call_args
                assert "extra_body" not in kwargs

    def test_llm_chat_extra_body_for_deepseek(self):
        """llm_chat disables reasoning for STELINT_LLM_TYPE=deepseek."""
        with patch.dict(os.environ, {"STELINT_LLM_BASE_URL": "http://test:9999/v1", "STELINT_LLM_TYPE": "deepseek"}):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint.llm_client import llm_chat

                stelint.llm_client._client = None
                llm_chat([{"role": "user", "content": "hi"}])
                _, kwargs = mock_client.chat.completions.create.call_args
                assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    def test_request_timeout_default(self):
        """Client timeout defaults to 60 seconds."""
        with patch.dict(os.environ, {"STELINT_LLM_BASE_URL": "http://test:9999/v1"}, clear=True):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint import llm_client

                llm_client._client = None
                llm_client.get_llm_client()
                _, kwargs = mock_openai.OpenAI.call_args
                assert kwargs["timeout"] == 60.0

    def test_request_timeout_env_var(self):
        """STELINT_LLM_TIMEOUT overrides the client request timeout."""
        with patch.dict(os.environ, {"STELINT_LLM_BASE_URL": "http://test:9999/v1", "STELINT_LLM_TIMEOUT": "120"}, clear=True):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint import llm_client

                llm_client._client = None
                llm_client.get_llm_client()
                _, kwargs = mock_openai.OpenAI.call_args
                assert kwargs["timeout"] == 120.0

    def test_thinking_on_skips_extra_body(self):
        """STELINT_LLM_THINKING=on keeps reasoning on with a known type."""
        with patch.dict(
            os.environ,
            {"STELINT_LLM_BASE_URL": "http://test:9999/v1", "STELINT_LLM_TYPE": "vllm", "STELINT_LLM_THINKING": "on"},
            clear=True,
        ):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint.llm_client import llm_chat

                stelint.llm_client._client = None
                llm_chat([{"role": "user", "content": "hi"}])
                _, kwargs = mock_client.chat.completions.create.call_args
                assert "extra_body" not in kwargs

    def test_thinking_off_sends_extra_body(self):
        """STELINT_LLM_THINKING=off disables reasoning with a known type."""
        with patch.dict(
            os.environ,
            {"STELINT_LLM_BASE_URL": "http://test:9999/v1", "STELINT_LLM_TYPE": "vllm", "STELINT_LLM_THINKING": "off"},
            clear=True,
        ):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint.llm_client import llm_chat

                stelint.llm_client._client = None
                llm_chat([{"role": "user", "content": "hi"}])
                _, kwargs = mock_client.chat.completions.create.call_args
                assert kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}

    def test_thinking_invalid_value_uses_default(self):
        """An invalid STELINT_LLM_THINKING value falls back to the type behavior."""
        with patch.dict(
            os.environ,
            {"STELINT_LLM_BASE_URL": "http://test:9999/v1", "STELINT_LLM_TYPE": "deepseek", "STELINT_LLM_THINKING": "maybe"},
            clear=True,
        ):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint.llm_client import llm_chat

                stelint.llm_client._client = None
                llm_chat([{"role": "user", "content": "hi"}])
                _, kwargs = mock_client.chat.completions.create.call_args
                assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    def test_thinking_on_without_type_sends_no_body(self):
        """STELINT_LLM_THINKING=on without a type sends no extra_body."""
        with patch.dict(os.environ, {"STELINT_LLM_BASE_URL": "http://test:9999/v1", "STELINT_LLM_THINKING": "on"}, clear=True):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint.llm_client import llm_chat

                stelint.llm_client._client = None
                llm_chat([{"role": "user", "content": "hi"}])
                _, kwargs = mock_client.chat.completions.create.call_args
                assert "extra_body" not in kwargs

    def test_llm_chat_extra_body_type_is_case_insensitive(self):
        """STELINT_LLM_TYPE matches case-insensitively (VLLM -> vllm body)."""
        with patch.dict(os.environ, {"STELINT_LLM_BASE_URL": "http://test:9999/v1", "STELINT_LLM_TYPE": "VLLM"}):
            mock_openai, mock_client = self._mock_chat_client()
            with patch.dict(sys.modules, {"openai": mock_openai}):
                from stelint.llm_client import llm_chat

                stelint.llm_client._client = None
                llm_chat([{"role": "user", "content": "hi"}])
                _, kwargs = mock_client.chat.completions.create.call_args
                assert kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


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


class _FakeSense2Vec:
    """Minimal stand-in for the sense2vec model.

    Entries use the model key format "lemma|sense".
    """

    def __init__(self, entries):
        self._entries = set(entries)
        self.senses = sorted({e.split("|", 1)[1] for e in entries})

    def __contains__(self, key):
        return key in self._entries


class TestCollectCandidates:
    """Tests for the local candidate preprocessing step."""

    def setup_method(self):
        """Load spaCy model for each test."""
        self.nlp = spacy.load("en_core_web_sm")

    def test_collect_candidates_basic_filters(self):
        """Rare words and mixed-POS words are excluded; rest are kept sorted."""
        from stelint.checks_llm import _collect_candidates

        doc = self.nlp("Run the test. Run the pump. Run the fan. The container holds data. The container stores files. Turn on the light. The package is light.")
        candidates = _collect_candidates(doc)
        lemmas = [c.lemma for c in candidates]
        assert lemmas == sorted(lemmas)
        assert "run" in lemmas
        assert "container" not in lemmas  # only 2 occurrences
        assert "light" not in lemmas  # NOUN + ADJ, handled by spaCy checks

    def test_monosemous_word_skipped_with_sense_model(self):
        """A word with a single sense entry is skipped without an LLM call."""
        from stelint import checks_llm

        doc = self.nlp("Check the valve. The valve is open. Close the valve.")
        fake_model = _FakeSense2Vec(["valve|noun"])
        with patch("stelint.checks_llm._sense2vec_model", fake_model):
            with patch("stelint.checks_llm.llm_chat") as mock_chat:
                with patch("stelint.checks_llm.get_llm_client", return_value=MagicMock()):
                    result = checks_llm.check_llm_polysemy(doc)
        assert result == []
        mock_chat.assert_not_called()

    def test_polysemous_word_kept_with_sense_model(self):
        """A word with two or more sense entries is kept as a candidate."""
        from stelint import checks_llm

        doc = self.nlp("Check the valve. The valve is open. Close the valve.")
        fake_model = _FakeSense2Vec(["valve|noun", "valve|verb"])
        with patch("stelint.checks_llm._sense2vec_model", fake_model):
            with patch("stelint.checks_llm.llm_chat", return_value="'valve': SAME") as mock_chat:
                with patch("stelint.checks_llm.get_llm_client", return_value=MagicMock()):
                    result = checks_llm.check_llm_polysemy(doc)
        assert result == []  # LLM says SAME
        mock_chat.assert_called_once()

    def test_context_sentences_capped(self):
        """At most _MAX_CONTEXTS_PER_WORD sentences per word in the prompt."""
        from stelint import checks_llm

        doc = self.nlp("Run the test. Run the pump. Run the fan. Run the light. Run the motor. Run the valve.")
        with patch("stelint.checks_llm.llm_chat", return_value="'run': SAME") as mock_chat:
            with patch("stelint.checks_llm.get_llm_client", return_value=MagicMock()):
                checks_llm.check_llm_polysemy(doc)
        prompt = mock_chat.call_args[0][0][0]["content"]
        context_lines = [line for line in prompt.split("\n") if re.match(r"^\s+\d+\. ", line)]
        assert len(context_lines) == checks_llm._MAX_CONTEXTS_PER_WORD

    def test_batching_splits_candidates(self):
        """Candidates are processed in batches of _BATCH_SIZE per LLM call."""
        from stelint import checks_llm

        doc = self.nlp(
            "Run the test. Run the pump. Run the fan. Check the valve. Check the seal. Check the joint. Set the limit. Set the rate. Set the bias. Hold the part. Hold the pin. Hold the clip."
        )
        with patch.object(checks_llm, "_BATCH_SIZE", 2):
            with patch("stelint.checks_llm.llm_chat", return_value="SAME") as mock_chat:
                with patch("stelint.checks_llm.get_llm_client", return_value=MagicMock()):
                    checks_llm.check_llm_polysemy(doc)
        # 4 candidates / batch size 2 = 2 LLM calls.
        assert mock_chat.call_count == 2

    def test_context_window_contains_word(self):
        """Long sentences are cut around the word; the word stays visible."""
        from stelint import checks_llm

        doc = self.nlp("The quick brown fox jumps over the lazy dog and keeps running through the long field of wild grass. Run the test. Run the pump. Run the fan.")
        tokens = [t for t in doc if t.lemma_.lower() == "run"]
        windows = checks_llm._context_sentences(tokens)
        assert any("running" in w for w in windows)
        for w in windows:
            assert len(w) <= checks_llm._CONTEXT_CHAR_LIMIT

    def test_parser_header_echo_format(self):
        """Parser recovers verdicts from echoed 'Word: x' headers."""
        from stelint.checks_llm import _parse_polysemy_response

        text = "Word: 'run'\nDIFFERENT: execute vs manage\n\nWord: 'set'\nSAME"
        results = _parse_polysemy_response(text, ["run", "set"])
        assert results["run"].startswith("DIFFERENT")
        assert results["set"].startswith("SAME")

    def test_batch_token_budget(self):
        """Each batch call uses the capped token budget."""
        from stelint import checks_llm

        doc = self.nlp("Run the test. Run the pump. Run the fan.")
        with patch("stelint.checks_llm.llm_chat", return_value="'run': SAME") as mock_chat:
            with patch("stelint.checks_llm.get_llm_client", return_value=MagicMock()):
                checks_llm.check_llm_polysemy(doc)
        _, kwargs = mock_chat.call_args
        assert kwargs["max_tokens"] == checks_llm._MAX_TOKENS_PER_BATCH


# Import the llm_client module at module level for test references.
import stelint.llm_client
