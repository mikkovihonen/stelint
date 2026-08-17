"""LLM-powered ASD-STE100 checks.

These checks use a large language model to detect issues that spaCy-based
heuristic checks cannot reliably find. Currently provides:

- LLMPolysemy: Detects words used with different meanings across the document,
  even when the part of speech is the same (which spaCy misses).

All functions are no-ops when the LLM is not configured (no STELINT_LLM_* env
vars set), allowing stelint to operate normally without it.
"""

import re
import sys

from .llm_client import get_llm_client, llm_chat

# Words appearing fewer than this many times are skipped to avoid noise.
_MIN_OCCURRENCES = 3

# Batch size: number of words per LLM call to amortize latency.
_BATCH_SIZE = 5


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

    # Step 1: Collect all content word occurrences (skip PROPN, stop words).
    occurrences: dict[str, list] = {}
    for token in doc:
        if token.pos_ == "PROPN" or token.is_stop:
            continue
        if not token.is_alpha or len(token.lemma_) <= 1:
            continue

        lemma = token.lemma_.lower()
        if lemma not in occurrences:
            occurrences[lemma] = []
        occurrences[lemma].append(token)

    # Step 2: Filter to words appearing >= _MIN_OCCURRENCES times.
    candidates = {w: toks for w, toks in occurrences.items() if len(toks) >= _MIN_OCCURRENCES}

    if not candidates:
        return []

    # Step 3: Skip words that spaCy already flags (different POS = different meaning).
    # These are handled by the existing check_key_words / _is_polysemous check.
    candidates = {lemma: toks for lemma, toks in candidates.items() if len({t.pos_ for t in toks}) == 1}

    if not candidates:
        return []

    # Step 4: Group by lemma and collect one context sentence per occurrence.
    lemma_sentences: dict[str, list[str]] = {}
    for lemma, toks in candidates.items():
        sentences: list[str] = []
        for token in toks:
            sent_text = token.sent.text.strip().rstrip(".")
            # Truncate very long sentences to keep prompts manageable.
            if len(sent_text) > 120:
                sent_text = sent_text[:117] + "..."
            if sent_text not in sentences:
                sentences.append(sent_text)
        lemma_sentences[lemma] = sentences

    # Step 5: Process in batches to amortize LLM latency.
    lemmas = list(candidates.keys())
    if len(lemmas) > 1:
        print(f"stelint: LLM check: analyzing {len(lemmas)} polysemous candidates...", file=sys.stderr)
    issues: list[dict] = []

    for i in range(0, len(lemmas), _BATCH_SIZE):
        batch = lemmas[i : i + _BATCH_SIZE]
        results = _batch_polysemy_check(batch, lemma_sentences)

        for lemma in batch:
            result = results.get(lemma)
            if result and result.startswith("DIFFERENT"):
                toks = candidates[lemma]
                explanation = result.split(": ", 1)[1] if ": " in result else "different meanings"
                first = toks[0]
                issues.append(
                    {
                        "type": "LLMPolysemy",
                        "message": (f"Word '{lemma}' has different meanings in the document: {explanation}. Use consistent terminology."),
                        "offset": first.idx,
                        "length": len(first.text),
                    }
                )

    return issues


def _batch_polysemy_check(lemmas: list[str], lemma_sentences: dict[str, list[str]]) -> dict[str, str]:
    """Send a batched prompt for multiple words and parse results.

    Args:
        lemmas: List of word lemmas to check in this batch.
        lemma_sentences: Mapping of lemma to its context sentences.

    Returns:
        Dictionary of {lemma: "SAME" or "DIFFERENT: ..."} results.
    """
    prompt_parts: list[str] = []
    for lemma in lemmas:
        sentences = lemma_sentences[lemma]
        ctx_lines = "\n".join(f"  {i + 1}. '{s}'" for i, s in enumerate(sentences))
        prompt_parts.append(f"Word: '{lemma}'\n{ctx_lines}\n")

    prompt = (
        "You are an ASD-STE100 Simplified Technical English expert.\n"
        "For each word, determine if it has the SAME meaning or DIFFERENT meanings.\n\n" + "\n---\n\n".join(prompt_parts) + "\n\nAnswer in this format for each word:\n"
        "'lemma': SAME  OR  'lemma': DIFFERENT: <explanation>"
    )

    result_text = llm_chat([{"role": "user", "content": prompt}], max_tokens=4000)

    if not result_text:
        return {}

    results: dict[str, str] = {}

    # Try structured format first: 'lemma': SAME or 'lemma': DIFFERENT: ...
    for line in result_text.split("\n"):
        line = line.strip().strip("'")
        if ": " in line:
            word, verdict = line.split(": ", 1)
            word = word.strip("'").strip()
            verdict = verdict.strip()
            if verdict.startswith("SAME") or verdict.startswith("DIFFERENT"):
                results[word] = verdict

    # If structured parsing found nothing, try to find lemma: verdict pairs
    # in the raw text (handles reasoning models that embed answers in thinking).
    if not results:
        for lemma in lemmas:
            # Look for the lemma followed by SAME or DIFFERENT nearby
            pattern = re.escape(lemma) + r"[\s:]+(SAME|DIFFERENT(?:\s*:\s*.*)?)"
            match = re.search(pattern, result_text, re.IGNORECASE)
            if match:
                results[lemma] = match.group(1).strip()

    return results
