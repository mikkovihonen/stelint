"""LLM-powered ASD-STE100 checks.

These checks use a large language model to detect issues that spaCy-based
heuristic checks cannot reliably find. Currently provides:

- LLMPolysemy: Detects words used with different meanings across the document,
  even when the part of speech is the same (which spaCy misses).

Candidate collection is a local preprocessing step (no LLM calls). It keeps
only words that plausibly need LLM analysis:

- the word appears at least _MIN_OCCURRENCES times,
- all occurrences have the same part of speech (different POS is already
  handled by the spaCy checks),
- the word is not a proper noun, stop word, or single-letter word,
- if the optional sense2vec model is available (STELINT_S2V_PATH), the word
  is not known to the model with exactly one sense (a monosemous word
  cannot be polysemous).

Candidates are then processed in compact batches to minimize LLM calls and
token usage.

All functions are no-ops when the LLM is not configured (no STELINT_LLM_* env
vars set), allowing stelint to operate normally without it.
"""

import re
import sys
from dataclasses import dataclass, field

from .checks_section6 import s2v_model as _sense2vec_model
from .llm_client import get_llm_client, llm_chat

# Words appearing fewer than this many times are skipped to avoid noise.
_MIN_OCCURRENCES = 3

# Number of words per LLM call. Small batches keep each call short enough
# for slow or reasoning models (which think longer on bigger batches), and
# a failed batch only loses its own words.
_BATCH_SIZE = 5

# Maximum context sentences shown per word. More examples do not improve
# the LLM verdict and only grow the prompt.
_MAX_CONTEXTS_PER_WORD = 4

# Maximum characters per context sentence in the prompt.
_CONTEXT_CHAR_LIMIT = 80

# Token budget per batch: one verdict line per word plus reasoning headroom.
# Capping this bounds call duration on reasoning models.
_MAX_TOKENS_PER_BATCH = 1000


@dataclass
class _Candidate:
    """A word candidate for LLM polysemy analysis.

    Attributes:
        lemma: Lowercased lemma of the word.
        tokens: All spaCy tokens of the word in the document.
    """

    lemma: str
    tokens: list = field(default_factory=list)


def _collect_candidates(doc) -> list[_Candidate]:
    """Collect words that may be polysemous, using local information only.

    This preprocessing step makes no LLM calls. See the module docstring
    for the filter rules.

    Args:
        doc: A spaCy Doc object.

    Returns:
        List of _Candidate objects, sorted by lemma.
    """
    occurrences: dict[str, list] = {}
    for token in doc:
        if token.pos_ == "PROPN" or token.is_stop:
            continue
        if not token.is_alpha or len(token.lemma_) <= 1:
            continue

        lemma = token.lemma_.lower()
        occurrences.setdefault(lemma, []).append(token)

    candidates = []
    for lemma, tokens in occurrences.items():
        if len(tokens) < _MIN_OCCURRENCES:
            continue
        # Same POS in every occurrence: different POS is already flagged
        # by the spaCy checks (check_key_words / _is_polysemous).
        if len({t.pos_ for t in tokens}) != 1:
            continue
        # Sense info (if available): a word the sense model knows with
        # exactly one sense cannot be polysemous.
        if _is_monosemous(lemma):
            continue
        candidates.append(_Candidate(lemma, tokens))

    candidates.sort(key=lambda c: c.lemma)
    return candidates


def _is_monosemous(lemma: str) -> bool:
    """Check if the sense2vec model knows exactly one sense of the word.

    Sense information is only available when the optional sense2vec model
    is installed. Without it, no word can be ruled out locally.

    Args:
        lemma: Lowercased word lemma.

    Returns:
        True if the model is available and the word has a single sense
        entry; False otherwise.
    """
    model = _sense2vec_model
    if model is None:
        return False

    count = 0
    for sense in model.senses:
        if f"{lemma}|{sense}" in model:
            count += 1
            if count > 1:
                return False
    return count == 1


def _context_sentences(tokens: list) -> list[str]:
    """Collect up to _MAX_CONTEXTS_PER_WORD distinct context windows.

    Each window is the sentence of one occurrence, shortened to
    _CONTEXT_CHAR_LIMIT characters around the word itself. The word is
    always visible in its window: a plain prefix truncation would cut the
    word off in long sentences and the LLM could not judge it.

    Args:
        tokens: spaCy tokens of one word.

    Returns:
        List of de-duplicated context window texts.
    """
    sentences: list[str] = []
    for token in tokens:
        raw_sent = token.sent.text
        # Character offset of the word inside the stripped sentence.
        word_start = token.idx - token.sent.start_char
        sent_text = raw_sent.strip()
        word_start -= len(raw_sent) - len(raw_sent.lstrip())
        if len(sent_text) > _CONTEXT_CHAR_LIMIT:
            half = _CONTEXT_CHAR_LIMIT // 2
            w_start = max(0, word_start - half)
            w_end = min(len(sent_text), w_start + _CONTEXT_CHAR_LIMIT)
            w_start = max(0, w_end - _CONTEXT_CHAR_LIMIT)
            sent_text = sent_text[w_start:w_end]
        sent_text = sent_text.strip(" .")
        if sent_text and sent_text not in sentences:
            sentences.append(sent_text)
        if len(sentences) >= _MAX_CONTEXTS_PER_WORD:
            break
    return sentences


def check_llm_polysemy(doc) -> list[dict]:
    """Check for cross-document polysemy using the LLM.

    Detects words used with different meanings in different parts of the
    document, even when the part of speech is the same (which spaCy cannot
    distinguish). spaCy-detected polysemy (different POS tags) is skipped
    since the existing check_key_words check already handles that.

    Args:
        doc: A spaCy Doc object of the cleaned text.

    Returns:
        List of issue dicts with keys: type, message, offset, length.
        Empty list if LLM is not configured or no issues found.
    """
    if get_llm_client() is None:
        return []

    candidates = _collect_candidates(doc)
    if not candidates:
        return []

    if len(candidates) > 1:
        total = sum(len(c.tokens) for c in candidates)
        print(
            f"stelint: LLM check: analyzing {len(candidates)} polysemy candidates ({total} occurrences)...",
            file=sys.stderr,
        )

    issues: list[dict] = []
    for i in range(0, len(candidates), _BATCH_SIZE):
        batch = candidates[i : i + _BATCH_SIZE]
        results = _batch_polysemy_check(batch)

        for cand in batch:
            result = results.get(cand.lemma)
            if result and result.startswith("DIFFERENT"):
                explanation = result.split(": ", 1)[1] if ": " in result else "different meanings"
                first = cand.tokens[0]
                issues.append(
                    {
                        "type": "LLMPolysemy",
                        "message": (f"Word '{cand.lemma}' has different meanings in the document: {explanation}. Use consistent terminology."),
                        "offset": first.idx,
                        "length": len(first.text),
                    }
                )

    return issues


def _batch_polysemy_check(candidates: list[_Candidate]) -> dict[str, str]:
    """Send a batched prompt for multiple words and parse results.

    Args:
        candidates: Word candidates to check in this batch.

    Returns:
        Dictionary of {lemma: "SAME" or "DIFFERENT: ..."} results.
    """
    prompt_parts: list[str] = []
    for cand in candidates:
        sentences = _context_sentences(cand.tokens)
        ctx_lines = "\n".join(f"  {i + 1}. '{s}'" for i, s in enumerate(sentences))
        prompt_parts.append(f"Word: '{cand.lemma}'\n{ctx_lines}\n")

    prompt = (
        "You are an ASD-STE100 Simplified Technical English expert.\n"
        "For each word, determine if it has the SAME meaning or DIFFERENT meanings.\n\n" + "\n---\n\n".join(prompt_parts) + "\n\nAnswer in this format for each word:\n"
        "'lemma': SAME  OR  'lemma': DIFFERENT: <explanation>"
    )

    result_text = llm_chat([{"role": "user", "content": prompt}], max_tokens=_MAX_TOKENS_PER_BATCH)

    if not result_text:
        return {}

    return _parse_polysemy_response(result_text, [c.lemma for c in candidates])


def _parse_polysemy_response(result_text: str, lemmas: list[str]) -> dict[str, str]:
    """Parse an LLM response into {lemma: verdict} results.

    Tries three formats in order:
    1. Structured lines: 'lemma': SAME  or  'lemma': DIFFERENT: ...
    2. A lemma followed by SAME/DIFFERENT anywhere in the text
       (reasoning models may embed the answer in their thinking).
    3. A quoted word header on one line with the verdict on the next
       line (models that echo the prompt headers in their answer).

    Args:
        result_text: Raw LLM response text.
        lemmas: Candidate lemmas of the batch.

    Returns:
        Dictionary of {lemma: "SAME" or "DIFFERENT: ..."} results.
    """
    results: dict[str, str] = {}

    # Format 1: structured lines.
    for line in result_text.split("\n"):
        line = line.strip().strip("'")
        if ": " in line:
            word, verdict = line.split(": ", 1)
            word = word.strip("'").strip()
            verdict = verdict.strip()
            if verdict.startswith("SAME") or verdict.startswith("DIFFERENT"):
                results[word] = verdict

    # Format 2: lemma followed by SAME or DIFFERENT in the raw text.
    if not results:
        for lemma in lemmas:
            pattern = re.escape(lemma) + r"[\s:]+(SAME|DIFFERENT(?:\s*:\s*.*)?)"
            match = re.search(pattern, result_text, re.IGNORECASE)
            if match:
                results[lemma] = match.group(1).strip()

    # Format 3: quoted word header, verdict on the next line.
    if not results:
        pattern = r"'([A-Za-z0-9_]+)'\s*\n\s*(SAME|DIFFERENT(?:\s*:\s*.*)?)"
        for match in re.finditer(pattern, result_text, re.IGNORECASE):
            results[match.group(1).lower()] = match.group(2).strip()

    return results
