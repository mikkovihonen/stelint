"""Tests for local classifier subsystem and tokenizer."""

from unittest.mock import MagicMock, patch

import numpy as np
import spacy

from stelint.classifier.model_loader import (
    ENV_STELINT_MODEL_PATH,
    get_cache_dir,
    get_model_path,
    is_model_available,
)
from stelint.classifier.onnx_runner import (
    CrossEncoderClassifier,
    softmax,
)
from stelint.classifier.tokenizer import SimpleTokenizer


class TestSimpleTokenizer:
    """Unit tests for the SimpleTokenizer."""

    def test_basic_tokenize(self):
        tokenizer = SimpleTokenizer()
        tokens = tokenizer.tokenize("Open the valve.")
        assert tokens == ["open", "the", "valve", "."]

    def test_encode_pair(self):
        tokenizer = SimpleTokenizer()
        input_ids, attention_mask, token_type_ids = tokenizer.encode_pair("Rule: VerbForms", "The running gear is lubricated.", max_length=16)
        assert len(input_ids) == 16
        assert len(attention_mask) == 16
        assert len(token_type_ids) == 16
        assert input_ids[0] == tokenizer.cls_id
        assert tokenizer.sep_id in input_ids

    def test_batch_encode_pairs(self):
        tokenizer = SimpleTokenizer()
        pairs = [
            ("Rule: VerbForms | Word: running", "The running gear drives the shaft."),
            ("Rule: MissingArticles | Word: valve", "Open valve now."),
        ]
        batch = tokenizer.batch_encode_pairs(pairs, max_length=32)
        assert "input_ids" in batch
        assert "attention_mask" in batch
        assert "token_type_ids" in batch
        assert batch["input_ids"].shape == (2, 32)


class TestModelLoader:
    """Unit tests for model discovery and path resolution."""

    def test_get_cache_dir(self):
        cache_dir = get_cache_dir()
        assert "stelint" in str(cache_dir)
        assert cache_dir.exists()

    def test_env_model_path_override(self, tmp_path):
        dummy_model = tmp_path / "custom_model.onnx"
        dummy_model.write_text("dummy")

        with patch.dict("os.environ", {ENV_STELINT_MODEL_PATH: str(dummy_model)}):
            assert get_model_path() == str(dummy_model)
            assert is_model_available() is True


class TestCrossEncoderClassifier:
    """Unit tests for ONNX classifier execution and issue filtering."""

    def test_softmax(self):
        logits = np.array([[2.0, 1.0], [0.0, 0.0]])
        probs = softmax(logits)
        assert np.isclose(np.sum(probs[0]), 1.0)
        assert np.isclose(np.sum(probs[1]), 1.0)
        assert probs[0][0] > probs[0][1]

    @patch("onnxruntime.InferenceSession")
    def test_predict_batch_mock(self, mock_session_cls):
        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input_ids"
        mock_session.get_inputs.return_value = [mock_input]
        mock_output = MagicMock()
        mock_output.name = "logits"
        mock_session.get_outputs.return_value = [mock_output]

        # Return logits where item 1 = TP (class 0 high), item 2 = FP (class 1 high)
        mock_session.run.return_value = [np.array([[3.0, -1.0], [-1.0, 3.0]])]
        mock_session_cls.return_value = mock_session

        classifier = CrossEncoderClassifier(model_path="dummy.onnx")
        items = [
            {"rule": "MissingArticles", "word": "valve", "sentence": "Open valve."},
            {"rule": "MissingArticles", "word": "Filters", "sentence": "Filters are clean."},
        ]
        preds = classifier.predict_batch(items)
        assert len(preds) == 2
        assert preds[0]["prob_tp"] > preds[0]["prob_fp"]  # Genuine error (TP)
        assert preds[1]["prob_fp"] > preds[1]["prob_tp"]  # False positive (FP)

    @patch("onnxruntime.InferenceSession")
    def test_filter_issues(self, mock_session_cls):
        nlp = spacy.load("en_core_web_sm")
        doc = nlp("Open valve. Filters are clean.")

        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input_ids"
        mock_session.get_inputs.return_value = [mock_input]
        mock_output = MagicMock()
        mock_output.name = "logits"
        mock_session.get_outputs.return_value = [mock_output]

        # Return logits: first item is TP (kept), second item is FP with 0.95 prob (suppressed)
        mock_session.run.return_value = [np.array([[3.0, -2.0], [-3.0, 3.0]])]
        mock_session_cls.return_value = mock_session

        classifier = CrossEncoderClassifier(model_path="dummy.onnx")
        issues = [
            {"type": "MissingArticles", "message": "valve", "offset": 5, "length": 5},
            {"type": "MissingArticles", "message": "Filters", "offset": 12, "length": 7},
        ]
        confirmed, suppressed = classifier.filter_issues(issues, doc)
        assert len(confirmed) == 1
        assert confirmed[0]["offset"] == 5
        assert len(suppressed) == 1
        assert suppressed[0]["offset"] == 12
