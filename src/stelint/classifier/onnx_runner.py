"""ONNX Runtime Cross-Encoder Sequence Classifier.

Provides fast, CPU-efficient, calibrated inference for false positive filtering.
"""

from __future__ import annotations

import sys
from typing import Any

import numpy as np

from .model_loader import get_model_path, get_vocab_path
from .tokenizer import SimpleTokenizer

# Default per-rule confidence threshold for suppressing an issue as False Positive.
# If P(False Positive) > threshold, the issue is suppressed.
# High thresholds (0.80-0.85) ensure high recall for genuine errors.
DEFAULT_FP_THRESHOLDS: dict[str, float] = {
    "VerbForms": 0.85,
    "ConnectingWords": 0.80,
    "PartOfSpeech": 0.80,
    "TechnicalVerbAsNoun": 0.85,
    "MissingArticles": 0.80,
}
DEFAULT_THRESHOLD = 0.80

_global_classifier: CrossEncoderClassifier | None = None


def softmax(logits: np.ndarray) -> np.ndarray:
    """Compute softmax probabilities along the last axis."""
    exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
    return exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)


class CrossEncoderClassifier:
    """ONNX-based Cross-Encoder for rule issue verification."""

    def __init__(self, model_path: str, vocab_path: str | None = None, session_options: Any = None):
        import onnxruntime as ort

        self.model_path = model_path
        opts = session_options or ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]

        if vocab_path:
            self.tokenizer = SimpleTokenizer.from_file(vocab_path)
        else:
            self.tokenizer = SimpleTokenizer()

    @classmethod
    def load_default(cls) -> CrossEncoderClassifier | None:
        """Load default classifier if model file is available."""
        model_path = get_model_path()
        if not model_path:
            return None

        vocab_path = get_vocab_path()
        try:
            return cls(model_path=model_path, vocab_path=vocab_path)
        except Exception as e:
            print(f"stelint: Failed to initialize ONNX classifier: {e}", file=sys.stderr)
            return None

    def predict_batch(self, items: list[dict[str, str]]) -> list[dict[str, float]]:
        """Predict True Positive vs False Positive probabilities for a batch of items.

        Args:
            items: List of dicts with keys:
                - 'rule': str (e.g. 'MissingArticles')
                - 'word': str (e.g. 'valve')
                - 'sentence': str (full sentence context)

        Returns:
            List of dicts with 'prob_tp' and 'prob_fp'.
        """
        if not items:
            return []

        pairs = []
        for item in items:
            text_a = f"Rule: {item.get('rule', '')} | Word: {item.get('word', '')}"
            text_b = item.get("sentence", "")
            pairs.append((text_a, text_b))

        encoded = self.tokenizer.batch_encode_pairs(pairs, max_length=128)

        feed_dict = {}
        if "input_ids" in self.input_names:
            feed_dict["input_ids"] = encoded["input_ids"]
        if "attention_mask" in self.input_names:
            feed_dict["attention_mask"] = encoded["attention_mask"]
        if "token_type_ids" in self.input_names:
            feed_dict["token_type_ids"] = encoded["token_type_ids"]

        outputs = self.session.run(self.output_names, feed_dict)
        logits = outputs[0]
        probs = softmax(logits)

        results = []
        for prob in probs:
            # Assuming class 0 = True Positive (genuine violation), class 1 = False Positive (compliant)
            p_tp = float(prob[0])
            p_fp = float(prob[1]) if len(prob) > 1 else float(1.0 - p_tp)
            results.append({"prob_tp": p_tp, "prob_fp": p_fp})

        return results

    def filter_issues(
        self,
        issues: list[dict],
        doc,
        thresholds: dict[str, float] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Filter a list of issues using the classifier.

        Args:
            issues: List of issue dicts from checks.
            doc: spaCy Doc object.
            thresholds: Optional dict mapping rule name to FP threshold.

        Returns:
            (confirmed_issues, suppressed_issues)
        """
        if not issues:
            return [], []

        rule_thresholds = thresholds or DEFAULT_FP_THRESHOLDS
        batch_items = []

        for issue in issues:
            offset = issue["offset"]
            length = issue.get("length", 1)
            token_text = doc.text[offset : offset + length] if offset < len(doc.text) else ""

            # Find sentence context
            sent_text = ""
            for sent in doc.sents:
                if sent.start_char <= offset < sent.end_char:
                    sent_text = sent.text.strip()
                    break
            if not sent_text and offset < len(doc.text):
                # Fallback to local window
                start = max(0, offset - 50)
                end = min(len(doc.text), offset + length + 50)
                sent_text = doc.text[start:end].strip()

            batch_items.append(
                {
                    "rule": issue["type"],
                    "word": token_text,
                    "sentence": sent_text,
                }
            )

        predictions = self.predict_batch(batch_items)

        confirmed: list[dict] = []
        suppressed: list[dict] = []

        for issue, pred in zip(issues, predictions):
            rule = issue["type"]
            threshold = rule_thresholds.get(rule, DEFAULT_THRESHOLD)
            prob_fp = pred["prob_fp"]

            if prob_fp > threshold:
                suppressed.append(issue)
            else:
                confirmed.append(issue)

        return confirmed, suppressed


def get_classifier() -> CrossEncoderClassifier | None:
    """Return the global CrossEncoderClassifier singleton, or None if unavailable."""
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = CrossEncoderClassifier.load_default()
    return _global_classifier
