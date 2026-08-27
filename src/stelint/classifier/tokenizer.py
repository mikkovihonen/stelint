"""Lightweight tokenizer for sequence classification inference.

Provides tokenization for transformer-based cross-encoder models without
requiring heavy dependencies like torch or transformers at inference time.
"""

from __future__ import annotations

import os
import re
from typing import Any


class SimpleTokenizer:
    """Fast tokenizer for cross-encoder sequence pair classification."""

    def __init__(self, vocab: dict[str, int] | None = None, unk_token: str = "[UNK]", cls_token: str = "[CLS]", sep_token: str = "[SEP]", pad_token: str = "[PAD]"):
        self.unk_token = unk_token
        self.cls_token = cls_token
        self.sep_token = sep_token
        self.pad_token = pad_token

        if vocab is not None:
            self.vocab = vocab
        else:
            self.vocab = self._build_basic_vocab()

        self.inv_vocab = {v: k for k, v in self.vocab.items()}
        self.unk_id = self.vocab.get(self.unk_token, 1)
        self.cls_id = self.vocab.get(self.cls_token, 2)
        self.sep_id = self.vocab.get(self.sep_token, 3)
        self.pad_id = self.vocab.get(self.pad_token, 0)

    def _build_basic_vocab(self) -> dict[str, int]:
        """Build standard initial vocabulary."""
        special_tokens = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
        vocab: dict[str, int] = {}
        for idx, tok in enumerate(special_tokens):
            vocab[tok] = idx
        return vocab

    @classmethod
    def from_file(cls, vocab_path: str) -> SimpleTokenizer:
        """Load vocabulary from a text file (one token per line) or JSON file."""
        if not os.path.exists(vocab_path):
            return cls()

        vocab: dict[str, int] = {}
        if vocab_path.endswith(".json"):
            import json

            with open(vocab_path, "r", encoding="utf-8") as f:
                vocab = json.load(f)
        else:
            with open(vocab_path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    token = line.strip()
                    if token:
                        vocab[token] = idx

        return cls(vocab=vocab)

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase words and punctuation tokens."""
        text = text.lower()
        # Separate punctuation from words
        tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        return tokens

    def encode_pair(
        self,
        text_a: str,
        text_b: str,
        max_length: int = 128,
    ) -> tuple[list[int], list[int], list[int]]:
        """Encode a pair of texts as [CLS] text_a [SEP] text_b [SEP].

        Returns:
            (input_ids, attention_mask, token_type_ids)
        """
        tokens_a = self.tokenize(text_a)
        tokens_b = self.tokenize(text_b)

        # Account for [CLS], [SEP], [SEP]
        available_len = max_length - 3
        if len(tokens_a) + len(tokens_b) > available_len:
            # Truncate text_b first, keeping text_a intact
            len_a = min(len(tokens_a), available_len // 2)
            len_b = available_len - len_a
            tokens_a = tokens_a[:len_a]
            tokens_b = tokens_b[:len_b]

        ids_a = [self.vocab.get(t, self.unk_id) for t in tokens_a]
        ids_b = [self.vocab.get(t, self.unk_id) for t in tokens_b]

        input_ids = [self.cls_id] + ids_a + [self.sep_id] + ids_b + [self.sep_id]
        token_type_ids = [0] * (len(ids_a) + 2) + [1] * (len(ids_b) + 1)
        attention_mask = [1] * len(input_ids)

        # Pad to max_length
        pad_len = max_length - len(input_ids)
        if pad_len > 0:
            input_ids += [self.pad_id] * pad_len
            token_type_ids += [0] * pad_len
            attention_mask += [0] * pad_len

        return input_ids[:max_length], attention_mask[:max_length], token_type_ids[:max_length]

    def batch_encode_pairs(
        self,
        pairs: list[tuple[str, str]],
        max_length: int = 128,
    ) -> dict[str, Any]:
        """Batch encode list of (text_a, text_b) pairs into numpy arrays."""
        import numpy as np

        all_input_ids = []
        all_attention_mask = []
        all_token_type_ids = []

        for text_a, text_b in pairs:
            input_ids, attention_mask, token_type_ids = self.encode_pair(text_a, text_b, max_length=max_length)
            all_input_ids.append(input_ids)
            all_attention_mask.append(attention_mask)
            all_token_type_ids.append(token_type_ids)

        return {
            "input_ids": np.array(all_input_ids, dtype=np.int64),
            "attention_mask": np.array(all_attention_mask, dtype=np.int64),
            "token_type_ids": np.array(all_token_type_ids, dtype=np.int64),
        }
