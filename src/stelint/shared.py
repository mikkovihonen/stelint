"""
Shared helper functions for ASD-STE100 checks.

This module contains utility functions that are used by multiple check modules.
These functions are not directly checking ASD-STE100 rules but provide common
functionality for the check functions.
"""

import spacy

# Load spaCy model once at module level for reuse
try:
    nlp = spacy.load("en_core_web_sm")
except (ImportError, OSError, RuntimeError):
    nlp = None


def _get_nlp():
    """Load spaCy model lazily to avoid import errors when model is not installed."""
    try:
        import spacy as spacy_module

        return spacy_module.load("en_core_web_sm")
    except OSError:
        return nlp


def _is_technical_context(token, doc):
    """Check if a token is in a technical context.

    Uses spaCy dependency parsing to determine if a word is part of a
    technical noun phrase or other technical construct.

    Args:
        token: spaCy Token object
        doc: spaCy Doc object

    Returns:
        bool: True if token is in a technical context
    """
    # Check if token is part of a noun chunk
    for chunk in doc.noun_chunks:
        if token in chunk:
            return True

    # Check if token is a compound modifier
    if token.dep_ == "compound":
        return True

    # Check if token is in a technical pattern (e.g., following technical nouns)
    return bool(token.head.pos_ == "NOUN" and token.head.dep_ in ("compound", "nn"))


def _get_context_words(token, doc, window=3):
    """Get context words around a token using spaCy dependency parsing.

    Uses token indexing and dependency relationships to extract context.

    Args:
        token: spaCy Token object
        doc: spaCy Doc object
        window: Number of words before and after to include (default: 3)

    Returns:
        list: List of context word lemmas
    """
    context_words = []

    # Get surrounding tokens in the sentence
    sent_start = token.sent.start
    sent_end = token.sent.end

    # Get up to window words before and after
    start = max(sent_start, token.i - window)
    end = min(sent_end, token.i + window + 1)

    for i in range(start, end):
        if i != token.i:
            t = doc[i]
            # Skip punctuation and stop words for context
            if t.is_alpha and not t.is_stop:
                context_words.append(t.lemma_.lower())

    return context_words


def _is_in_approved_context(token, doc, context_words, restricted_info):
    """Check if a word is used in an approved context.

    Uses spaCy dependency parsing and context analysis to determine
    if the word is being used with its approved meaning.

    Args:
        token: spaCy Token object
        doc: spaCy Doc object
        context_words: List of context word lemmas
        restricted_info: Dict with 'approved' and 'disapproved' context lists

    Returns:
        bool: True if word is used in approved context
    """
    approved_words = restricted_info.get("approved", [])
    disapproved_words = restricted_info.get("disapproved", [])

    # Check if any disapproved context words are present
    for disapproved in disapproved_words:
        if disapproved in context_words:
            return False

    # Check if token has approved dependencies
    # For example, "apply" should have a surface/object as dobj
    if token.pos_ == "VERB":
        for child in token.children:
            if child.dep_ in ("dobj", "attr"):
                child_text = child.text.lower()
                # Check if child is in approved list
                if any(approved in child_text for approved in approved_words):
                    return True
                # Check if child is in disapproved list
                if any(disapproved in child_text for disapproved in disapproved_words):
                    return False

    # If no clear disapproved context, assume it's approved
    # (conservative approach - only flag when we're sure)
    return True


def _get_sentence_depth(sent):
    """Calculate the maximum dependency depth of a sentence.

    Uses spaCy dependency parsing to traverse the dependency tree and
    calculate the maximum depth from any token to the root.

    Args:
        sent: spaCy Span object (sentence)

    Returns:
        int: Maximum dependency depth
    """
    max_depth = 0

    for token in sent:
        depth = _get_token_depth(token)
        max_depth = max(max_depth, depth)

    return max_depth


def _get_token_depth(token, visited=None):
    """Calculate the depth of a token in the dependency tree.

    Uses spaCy dependency parsing to traverse from the token to the root.

    Args:
        token: spaCy Token object
        visited: Set of visited token indices (to avoid infinite loops)

    Returns:
        int: Depth of the token in the dependency tree
    """
    if visited is None:
        visited = set()

    if token.head == token or token.idx in visited:
        return 0

    visited.add(token.idx)
    return 1 + _get_token_depth(token.head, visited)


def _get_first_content_word(sent):
    """Get the first content word (non-stop, non-punctuation) of a sentence.

    Uses spaCy features to identify content words and return the lemma
    of the first one found.

    Args:
        sent: spaCy Span object (sentence)

    Returns:
        str or None: Lemma of the first content word, or None if no content words
    """
    for token in sent:
        if not token.is_stop and token.pos_ != "PUNCT":
            return token.lemma_.lower()
    return None


def _has_connecting_word(sent, connecting_words):
    """Check if a sentence starts with a connecting word or phrase.

    Uses spaCy features to extract the first few tokens and check if they
    match any connecting words or phrases. This includes stop words like
    "also", "additionally", etc. which are common connecting words.

    Args:
        sent: spaCy Span object (sentence)
        connecting_words: Set of connecting words and phrases

    Returns:
        bool: True if sentence starts with a connecting word/phrase
    """
    # Get the first few tokens of the sentence (not just content words)
    # Connecting words like "also", "additionally" are often stop words
    first_tokens = []
    for token in sent:
        if token.pos_ == "PUNCT":
            continue  # Skip punctuation
        first_tokens.append(token.lemma_.lower())
        if len(first_tokens) >= 3:
            break

    # Check if any of the first tokens is a connecting word
    for word in first_tokens:
        if word in connecting_words:
            return True

    # Check if the first two tokens form a connecting phrase
    if len(first_tokens) >= 2:
        phrase = " ".join(first_tokens[:2])
        if phrase in connecting_words:
            return True

    return False


def _are_sentences_related(sent1, sent2, common_words=None):
    """Check if two sentences are related (simplified heuristic).

    Uses spaCy features to extract content words and calculate overlap
    between the two sentences. Filters out common words that don't indicate
    a meaningful relationship.

    Args:
        sent1: spaCy Span object (first sentence)
        sent2: spaCy Span object (second sentence)
        common_words: Optional set of words considered "common" (top X% by frequency).
            These words are filtered out from the overlap calculation.

    Returns:
        bool: True if sentences are related (have significant word overlap)
    """
    # Get content words from both sentences using helper
    words1 = _extract_content_words(sent1)
    words2 = _extract_content_words(sent2)

    # Calculate overlap
    if len(words1) == 0 or len(words2) == 0:
        return False

    # Filter out common words
    if common_words:
        filtered_words1 = words1 - common_words
        filtered_words2 = words2 - common_words
    else:
        filtered_words1 = words1
        filtered_words2 = words2

    # Recalculate with filtered words
    if len(filtered_words1) == 0 or len(filtered_words2) == 0:
        return False

    overlap = len(filtered_words1.intersection(filtered_words2))
    overlap_ratio = overlap / min(len(filtered_words1), len(filtered_words2))

    # If there's significant overlap, the sentences are likely related
    return overlap_ratio > 0.3


def _has_determiner_or_possessive(token) -> bool:
    """Check if a noun has an article, demonstrative, possessive, or determiner modifier."""
    for c in token.children:
        # Articles & demonstratives (the, a, an, this, that, these, those)
        if c.dep_ in ("det", "poss", "predet", "quantmod"):
            return True
        if c.tag_ in ("PRP$", "POS"):
            return True
        if c.pos_ == "DET":
            return True
        if c.pos_ == "PRON" and c.dep_ in ("poss", "det"):
            return True
        # Possessive construction like "John's" or "Stelint's" modifying this noun
        if c.dep_ == "compound" and any(gc.tag_ == "POS" for gc in c.children):
            return True
    return False


def _is_hyphenated_or_compound_fragment(token, doc) -> bool:
    """Check if token is part of a hyphenated compound or compound word fragment."""
    if token.text in ("-", "--", "—", "_"):
        return True
    if "-" in token.text or "_" in token.text:
        return True
    # Adjacent hyphen check
    if token.i > 0 and doc[token.i - 1].text in ("-", "--", "—"):
        return True
    if token.i + 1 < len(doc) and doc[token.i + 1].text in ("-", "--", "—"):
        return True
    return False


def _is_numbered_reference(token, doc) -> bool:
    """Check if token is part of a numbered entity reference (e.g. 'Section 6', 'Figure 2', 'Step 1')."""
    # Check if any child is a number modifier
    for c in token.children:
        if c.dep_ == "nummod" or c.pos_ == "NUM" or c.like_num:
            return True
    # Check if the immediately following token is a number or section identifier
    if token.i + 1 < len(doc):
        next_tok = doc[token.i + 1]
        if next_tok.pos_ == "NUM" or next_tok.like_num or (next_tok.text and next_tok.text[0].isdigit()):
            return True
    return False


def _is_uncountable_or_process_noun(token) -> bool:
    """Check if token is an uncountable mass noun or process noun using morphology and WordNet."""
    text_lower = token.text.lower()
    lemma_lower = token.lemma_.lower()

    # Gerunds and deverbal process nouns (-ing)
    if text_lower.endswith("ing") and (token.pos_ == "NOUN" or token.tag_ == "NN"):
        return True

    # Standard abstract and mass noun derivational suffixes
    abstract_suffixes = (
        "tion",
        "sion",
        "ment",
        "ance",
        "ence",
        "ity",
        "ness",
        "ware",
        "sis",
        "logy",
        "ics",
        "ism",
        "dom",
        "hood",
        "ship",
    )
    if text_lower.endswith(abstract_suffixes) or lemma_lower.endswith(abstract_suffixes):
        return True

    # Query WordNet for semantic category if available
    try:
        from nltk.corpus import wordnet as wn

        syns = wn.synsets(lemma_lower, pos=wn.NOUN)
        if syns:
            primary = syns[0]
            concrete_lexnames = {
                "noun.artifact",
                "noun.body",
                "noun.animal",
                "noun.plant",
                "noun.person",
                "noun.food",
                "noun.object",
                "noun.location",
            }
            if primary.lexname() not in concrete_lexnames:
                return True
    except (ImportError, LookupError):
        pass

    return False


def _is_idiomatic_prepositional_expression(token, doc) -> bool:
    """Check if token is part of a prepositional phrase functioning as an adverbial or predicative modifier."""
    if token.dep_ == "pobj":
        prep = token.head

        # Functional prepositions that inherently take bare nominals (e.g. per, via, as)
        if prep.pos_ == "ADP" and prep.text.lower() in ("per", "via"):
            return True

        if prep.text.lower() == "as":
            return True

        # Prepositional phrases acting as adverbial modifiers of verbs or adjectives
        if prep.dep_ in ("prep", "advmod", "npadvmod", "acl") and prep.head.pos_ in ("VERB", "ADJ", "AUX"):
            # Abstract nouns, technical terms, or compound nominals in adverbial PPs take zero article
            if _is_uncountable_or_process_noun(token) or _is_proper_noun_or_technical_term(token):
                return True
            if any(c.dep_ in ("compound", "amod") for c in token.children):
                return True

    return False


def _is_in_coordinate_or_enumerated_list(token, doc) -> bool:
    """Check if token is part of a coordinate list or enumeration sharing a determiner via the dependency tree."""
    if token.dep_ == "conj":
        head = token.head
        visited = set()
        while head and head.i not in visited:
            visited.add(head.i)
            # Head of the conjunction chain has a determiner
            if _has_determiner_or_possessive(head):
                return True
            # Preceding sibling conjunct in the same coordination chain has a determiner
            for sibling in head.children:
                if sibling.dep_ == "conj" and sibling.i < token.i and _has_determiner_or_possessive(sibling):
                    return True
            if head.dep_ == "conj":
                head = head.head
            else:
                break

    return False


def _is_quoted_or_parenthetical(token, doc) -> bool:
    """Check if token is a quoted example word or a single-word parenthetical."""
    punct_children = {c.text for c in token.children if c.pos_ == "PUNCT"}
    if ('"' in punct_children or "'" in punct_children or "`" in punct_children or "“" in punct_children or "‘" in punct_children) or (
        ("(" in punct_children and ")" in punct_children) or ("[" in punct_children and "]" in punct_children)
    ):
        return True

    if token.i > 0 and token.i + 1 < len(doc):
        prev_t = doc[token.i - 1].text
        next_t = doc[token.i + 1].text
        if (prev_t in ('"', "'", "`", "“", "‘", "*", "_") and next_t in ('"', "'", "`", "”", "’", "*", "_")) or (prev_t in ("(", "[") and next_t in (")", "]")):
            return True
    return False


def _is_proper_noun_or_technical_term(token) -> bool:
    """Check if token is a proper noun, acronym, or technical identifier via morphosyntax."""
    # Proper nouns tagged by spaCy
    if token.pos_ == "PROPN" or token.tag_ in ("NNP", "NNPS"):
        return True

    # Acronyms and initialisms (e.g. JSON, API, LLM, CLI, URL, POSIX, HTML)
    if token.text.isupper() and len(token.text) >= 2 and token.text.isalnum():
        return True

    # Technical identifiers with symbols or digits (e.g. stdin, stdout, config.yaml, x86_64, Model-740)
    if any(c in "_.-/0123456789" for c in token.text) and len(token.text) > 1:
        return True

    # Mixed-case or camelCase identifiers (e.g. spaCy, GitHub, DeepSeek)
    if any(c.isupper() for c in token.text[1:]):
        return True

    # Non-sentence-initial Titlecase tokens
    if token.text[0].isupper() and token.sent and token.i != token.sent.start:
        return True

    return False


def _is_likely_verb_misparse(token, doc) -> bool:
    """Check if a token tagged as NOUN is likely an imperative verb or predicate."""
    for c in token.children:
        if c.dep_ == "aux" and c.text.lower() == "to":
            return True
        if c.dep_ in ("xcomp", "advcl", "acl") and c.pos_ == "VERB":
            return True
    if token.dep_ == "conj" and token.head.pos_ in ("VERB", "AUX"):
        return True
    # Conjunction of a misparsed verb head: "Use - or pipe to read from stdin."
    # spaCy tags the imperative "Use" as NOUN (nsubj of the real verb "read").
    # Skip conjuncts of such a head. Do not walk further: in "Check valve and
    # pressure", "pressure" is a conj of noun "valve" (dobj of the verb) and
    # must stay flagged.
    if token.dep_ == "conj" and token.head.pos_ == "NOUN":
        head = token.head
        if head.dep_ in ("nsubj", "nsubjpass", "ROOT") and head.head.pos_ in ("VERB", "AUX"):
            return True
    return False


def _is_label_or_definition_header(token, doc) -> bool:
    """Check if token is part of a definition label before a colon (e.g. 'Output format:', 'Quiet mode:')."""
    if token.i + 1 < len(doc) and doc[token.i + 1].text == ":":
        return True
    for c in token.children:
        if c.text == ":" and c.i > token.i:
            return True
    return False


def _is_verbless_list_item_or_label(token, doc) -> bool:
    """Check if token is in a bullet item, table row fragment, or section label with no finite verb."""
    text = doc.text
    line_start = text.rfind("\n", 0, token.idx) + 1
    line_end = text.find("\n", token.idx) if text.find("\n", token.idx) != -1 else len(text)
    line_text = text[line_start:line_end]

    line_stripped = line_text.strip()
    if not line_stripped:
        return False

    line_tokens = [t for t in doc if line_start <= t.idx < line_end]
    has_finite_verb = any(t.pos_ in ("VERB", "AUX") and t.dep_ in ("ROOT", "ccomp", "advcl", "conj") and t.tag_ not in ("VBN", "VBG") for t in line_tokens)
    if not has_finite_verb:
        # Check if line had a list marker (leading spaces from markdown preprocessing) or is a fragment/heading
        if line_text.startswith(" ") or line_stripped.startswith(("-", "*", "+", "•", "Example", "Note")):
            return True

    return False


def _is_common_pattern_without_article(token, doc):
    """Check if a noun is in a common pattern that doesn't need an article.

    Rule 4.5 applies 'when applicable'. Many noun constructions in technical
    writing do not take articles.
    """
    # 1. Plural nouns in general statements (Rule 4.5 applies when applicable)
    if token.tag_ in ("NNS", "NNPS") or token.morph.get("Number") == ["Plur"]:
        return True

    # 2. Proper nouns, acronyms, and product/tool names
    if _is_proper_noun_or_technical_term(token):
        return True

    # 3. Hyphenated compounds / word fragments (e.g. "pre-filters", "case-insensitive")
    if _is_hyphenated_or_compound_fragment(token, doc):
        return True

    # 4. Numbered references ("Section 6", "Figure 2", "Step 3", "Rule 4.5")
    if _is_numbered_reference(token, doc):
        return True

    # 5. Coordinate lists sharing an article ("a proper noun, stop word, or single-letter word")
    if _is_in_coordinate_or_enumerated_list(token, doc):
        return True

    # 6. Quoted words or single-word parentheticals ("light" as NOUN, (thinking))
    if _is_quoted_or_parenthetical(token, doc):
        return True

    # 7. Uncountable mass nouns and process nouns (gerunds)
    if _is_uncountable_or_process_noun(token):
        return True

    # 8. Prepositional phrases without articles (e.g. "in JSON format", "by default")
    if _is_idiomatic_prepositional_expression(token, doc):
        return True

    # 9. Modifiers in compound nouns or followed by a head noun
    if token.dep_ in ("compound", "nn", "amod", "nmod", "npadvmod", "meta", "poss"):
        return True
    if token.i + 1 < len(doc) and doc[token.i + 1].pos_ in ("NOUN", "PROPN") and doc[token.i + 1].dep_ not in ("conj", "punct"):
        return True

    # 10. Single-character symbols / identifiers
    if len(token.text) == 1 and not token.text.isalnum():
        return True

    # 11. Verbs misparsed as nouns by spaCy
    if _is_likely_verb_misparse(token, doc):
        return True

    # 12. Labels before colons (e.g. "Output format: ...", "Quiet mode: ...")
    if _is_label_or_definition_header(token, doc):
        return True

    # 13. Verbless bullet list items / check labels (e.g. "- Past participle as adjective")
    if _is_verbless_list_item_or_label(token, doc):
        return True

    return False


def _get_paragraph_index(sent, doc):
    """Get the paragraph index of a sentence.

    Uses doc.text to split by paragraph breaks (\\n\\n) and find which paragraph
    the sentence belongs to based on its character offset.

    Args:
        sent: spaCy Sentence object
        doc: spaCy Doc object

    Returns:
        int: Paragraph index (0-based)
    """
    sent_start = sent.start_char
    paragraphs = doc.text.split("\n\n")

    current_offset = 0
    for para_idx, para in enumerate(paragraphs):
        para_end = current_offset + len(para)
        if current_offset <= sent_start <= para_end:
            return para_idx
        current_offset = para_end + 2  # +2 for \n\n

    return len(paragraphs)  # Default to last paragraph


def _get_compound_chain(hyphen_token, doc):
    """Get the chain of words connected by hyphens.

    Uses spaCy dependency parsing to find the full compound chain.

    Args:
        hyphen_token: spaCy Token object for the hyphen
        doc: spaCy Doc object

    Returns:
        list: List of tokens in the compound chain
    """
    chain = [hyphen_token]

    # Look backwards for connected words
    current = hyphen_token
    while True:
        # Check preceding token
        prev_idx = current.i - 1
        if prev_idx >= 0 and doc[prev_idx].text == "-":
            chain.insert(0, doc[prev_idx])
            current = doc[prev_idx]
        else:
            break

    # Look forwards for connected words
    current = hyphen_token
    while True:
        # Check following token
        next_idx = current.i + 1
        if next_idx < len(doc) and doc[next_idx].text == "-":
            chain.append(doc[next_idx])
            current = doc[next_idx]
        else:
            break

    return chain


def _find_matching_token(open_token, doc, open_char, close_char, return_index=False):
    """Find a matching closing token by tracking nesting depth.

    Generic function that can find matching parentheses, quotes, brackets, etc.
    by tracking the depth of nested open/close characters.

    Args:
        open_token: The opening token
        doc: spaCy Doc object or list of tokens
        open_char: The opening character to match (e.g., "(", "\"")
        close_char: The closing character to match (e.g., ")", "\"")
        return_index: If True, return the index instead of the token

    Returns:
        Token or int or None: The matching token/index, or None if not found
    """
    depth = 0

    # Check if doc is a spaCy Doc or a list of tokens
    is_doc = hasattr(doc, "__getitem__") and hasattr(doc[0], "text")

    if is_doc:
        # doc is a spaCy Doc object
        for token in doc[open_token.i :]:
            if token.text == open_char:
                depth += 1
            elif token.text == close_char:
                depth -= 1
                if depth == 0:
                    return token.i if return_index else token
    else:
        # doc is a list of tokens
        for i in range(open_token.i, len(doc)):
            token = doc[i]
            if token.text == open_char:
                depth += 1
            elif token.text == close_char:
                depth -= 1
                if depth == 0:
                    return i if return_index else token

    return None


def _find_closing_paren(open_paren_token, doc):
    """Find the closing parenthesis for an opening parenthesis.

    Uses token indexing and spaCy token positions.

    Args:
        open_paren_token: spaCy Token object for the opening parenthesis
        doc: spaCy Doc object (or list of tokens)

    Returns:
        spaCy Token or int: The closing parenthesis token (if doc is a Doc)
                           or index (if doc is a list), or None if not found
    """
    return _find_matching_token(open_paren_token, doc, "(", ")")


def _find_closing_quote(open_token, doc):
    """Find the closing quote for an opening quote.

    Uses token indexing and spaCy token positions.

    Args:
        open_token: The opening quote token
        doc: spaCy Doc object (or list of tokens)

    Returns:
        spaCy Token or int: The closing quote token (if doc is a Doc)
                           or index (if doc is a list), or None if not found
    """
    return _find_matching_token(open_token, doc, '"', '"')


def _is_allowed_parentheses_context(content, doc, offset):
    """Check if parentheses content is in an allowed context (Rule 8.3).

    Allowed contexts:
    - References to illustrations or text (e.g., "see Fig. 1")
    - Letters or numbers identifying items (e.g., "(a)", "(3)")
    - Work steps in procedures (e.g., "(1)", "(2)")
    - Abbreviations (e.g., "(kg)")
    - Singular and plural forms (e.g., "(s)")
    - Explanations (e.g., "(that is, ...)")
    - Alternatives (e.g., "(or ...)")

    Uses spaCy features:
    - token.ent_type_ for entity type detection (references to figures, etc.)
    - token.pos_ for part-of-speech tagging
    - Dependency parsing for relationship verification
    - NLP parsing for semantic analysis

    Args:
        content: Text inside parentheses
        doc: spaCy Doc object
        offset: Character offset of the opening parenthesis

    Returns:
        bool: True if parentheses usage is allowed
    """
    from .glossary import COMMON_ABBREVIATIONS, COMMON_UNITS

    # Parse the content with spaCy for semantic analysis
    nlp_instance = _get_nlp()
    if nlp_instance is None:
        return False
    content_doc = nlp_instance(content)

    # Check for references to illustrations or text using NER
    if content_doc.ents:
        for ent in content_doc.ents:
            # Check for figure, table, equation references
            if ent.label_ in ("WORK_OF_ART", "PRODUCT", "EVENT"):
                return True
            # Check for reference patterns
            content_words = _extract_content_words(content_doc)
            if content_words.intersection({"fig", "figure", "table", "eq", "chapter", "section"}):
                return True

    # Check for single letters or numbers (work steps, items)
    content_tokens = list(content_doc)
    if len(content_tokens) == 1:
        token = content_tokens[0]
        # Single letter
        if token.pos_ == "NOUN" and len(token.text) == 1 and token.text.isalpha():
            return True
        # Single number
        if token.pos_ == "NUM":
            return True

    # Check for abbreviations (short uppercase text)
    # Use spaCy POS tagging to verify it's likely an abbreviation
    if len(content_tokens) <= 2:
        # Check if all tokens are uppercase
        all_upper = all(t.is_upper for t in content_tokens if t.is_alpha)
        if all_upper and len(content) <= 5:
            # Check if it looks like an abbreviation (short, all caps)
            return True

        # Check if content matches common units or abbreviations
        content_lower = content.lower().strip()
        if content_lower in COMMON_UNITS or content_lower in COMMON_ABBREVIATIONS:
            return True

    # Check for alternatives (contains "or")
    # Note: "or" is a stop word, so we need to check the raw text
    if "or" in content.lower().split():
        return True

    # Check for explanations using dependency parsing
    # Note: Explanation words may include stop words, so check raw content
    content_lower = content.lower()
    if any(word in content_lower for word in ("that is", "i.e.", "meaning", "which means")):
        return True

    # Check for singular/plural forms using POS tagging
    # If content is a single word ending in 's' or 'es', it might be singular/plural
    if len(content_tokens) == 1:
        token = content_tokens[0]
        if token.pos_ == "NOUN" and (token.text.endswith("s") or token.text.endswith("es")):
            # Could be plural form, check if it's in allowed context
            return True

    return False


def _count_sentence_words(text):
    """Count words in a sentence according to ASD-STE100 word count rules.

    Rules:
    - Numbers count as one word
    - Numbers with units count as one word
    - Abbreviations count as one word
    - Hyphenated words count as one word
    - Parentheses content counts as one word
    - Punctuation is not counted
    - Quoted text counts as one word

    Uses spaCy features:
    - token.pos_ for part-of-speech tagging (NUM, PROPN, etc.)
    - token.ent_type_ for entity type detection
    - Dependency parsing for relationship verification
    - token.lemma_ for base form comparison
    - token.is_alpha for alpha detection

    Args:
        text: Sentence text

    Returns:
        int: Word count
    """
    from .glossary import COMMON_UNITS

    # Parse the text with spaCy
    nlp_instance = _get_nlp()
    if nlp_instance is None:
        return len(text.split())
    sent_doc = nlp_instance(text)

    # Track what to count as one word
    word_count = 0
    i = 0
    tokens = list(sent_doc)

    while i < len(tokens):
        token = tokens[i]

        # Skip punctuation using helper
        if token.pos_ == "PUNCT":
            i += 1
            continue

        # Count hyphenated words as one word
        if token.text == "-" or (token.text.startswith("-") and token.text != "-"):
            # Find the full hyphenated word
            hyphen_start = i
            while i < len(tokens) and (tokens[i].text == "-" or (tokens[i].text.startswith("-") and tokens[i].text != "-")):
                i += 1
            # Count the entire hyphenated sequence as one word
            if i > hyphen_start:
                word_count += 1
            continue

        # Count parenthesized content as one word
        if token.text == "(":
            # Find the closing parenthesis (tokens is a list, so _find_closing_paren returns index)
            close_idx = _find_closing_paren(token, tokens)
            if close_idx is not None:
                word_count += 1
                i = close_idx + 1
                continue

        # Count quoted text as one word
        if token.text in ('"', "'"):
            # Find the closing quote (tokens is a list, so _find_closing_quote returns index)
            close_idx = _find_closing_quote(token, tokens)
            if close_idx is not None:
                word_count += 1
                i = close_idx + 1
                continue

        # Count numbers as one word
        if token.pos_ == "NUM":
            word_count += 1
            # Check if next token is a unit (e.g., "kg", "mm")
            if i + 1 < len(tokens):
                next_token = tokens[i + 1]
                if next_token.pos_ == "NOUN" and next_token.text.lower() in COMMON_UNITS:
                    i += 1  # Skip the unit
            i += 1
            continue

        # Count proper nouns as one word
        if token.pos_ == "PROPN":
            word_count += 1
            i += 1
            continue

        # Count common nouns and other words
        if token.pos_ in ("NOUN", "VERB", "ADJ", "ADV", "PRON", "DET", "ADP", "CONJ", "CCONJ", "INTJ", "PART"):
            word_count += 1
        i += 1

    return word_count


def _find_closing_quote_idx(open_token, tokens):
    """Find the index of the closing quote.

    Wrapper around _find_closing_quote for backward compatibility.

    Args:
        open_token: The opening quote token
        tokens: List of tokens

    Returns:
        int: Index of the closing quote, or None if not found
    """
    result = _find_closing_quote(open_token, tokens)
    return result if isinstance(result, int) else None


def _get_restricted_verb_replacement(phrase):
    """Get the replacement for a restricted verb phrase.

    Uses a mapping of verb phrases to their approved replacements.

    Args:
        phrase: Tuple of (verb_lemma, preposition_lemma)

    Returns:
        str: Approved replacement, or None if no replacement found
    """
    from .glossary import RESTRICTED_VERB_PHRASES

    return RESTRICTED_VERB_PHRASES.get(phrase)


def _iter_content_tokens(doc):
    """Iterate over content tokens (non-punctuation, non-stop words, non-symbols).

    Generator function that yields only content tokens from a spaCy Doc,
    skipping punctuation, stop words, and symbol tokens (pos_=X includes
    markdown brackets, special characters, etc.).

    Args:
        doc: spaCy Doc object

    Yields:
        spaCy Token: Content tokens (non-punctuation, non-stop words, non-symbols)
    """
    for token in doc:
        # Skip stop words, punctuation, and symbols (pos_=X includes markdown brackets, etc.)
        if not token.is_stop and token.pos_ not in ("PUNCT", "X"):
            yield token


def _extract_content_words(doc):
    """Extract content words from a spaCy Doc.

    Returns a set of lowercase lemmas for all content tokens (non-punctuation, non-stop words).

    Args:
        doc: spaCy Doc object

    Returns:
        set: Set of lowercase lemma strings
    """
    return {token.lemma_.lower() for token in _iter_content_tokens(doc)}
