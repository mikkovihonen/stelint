"""Tests for Section 9 (Writing practices) checks."""

from stelint.checks_section9 import (
    check_consistent_style,
    check_consistent_terminology,
    check_different_sentence_constructions,
    check_non_approved_words,
    check_phrasal_verbs,
    check_word_for_word_replacement,
    check_word_usage,
)


class TestCheckWordUsage:
    """Tests for check_word_usage function."""

    def test_returns_list(self, nlp_model):
        """Test that function returns a list."""
        doc = nlp_model("The temperature go up by 10 degrees.")
        issues = check_word_usage(doc)
        assert isinstance(issues, list)

    def test_normal_text(self, nlp_model):
        """Test with normal text."""
        doc = nlp_model("Check the filter.")
        issues = check_word_usage(doc)
        assert isinstance(issues, list)


class TestCheckConsistentStyle:
    """Tests for check_consistent_style function."""

    def test_returns_list(self, nlp_model):
        """Test that function returns a list."""
        doc = nlp_model("The body is secure. The hull is tight.")
        issues = check_consistent_style(doc)
        assert isinstance(issues, list)

    def test_empty_doc(self, nlp_model):
        """Test with empty document."""
        doc = nlp_model("")
        issues = check_consistent_style(doc)
        assert isinstance(issues, list)


class TestCheckPhrasalVerbs:
    """Tests for check_phrasal_verbs function."""

    def test_returns_list(self, nlp_model):
        """Test that function returns a list."""
        doc = nlp_model("The temperature go up by 10 degrees.")
        issues = check_phrasal_verbs(doc)
        assert isinstance(issues, list)

    def test_normal_text(self, nlp_model):
        """Test with normal text."""
        doc = nlp_model("Check the filter.")
        issues = check_phrasal_verbs(doc)
        assert isinstance(issues, list)


class TestCheckConsistentTerminology:
    """Tests for check_consistent_terminology function."""

    def test_returns_list(self, nlp_model):
        """Test that function returns a list."""
        doc = nlp_model("The body assembly is secure.")
        issues = check_consistent_terminology(doc)
        assert isinstance(issues, list)


class TestCheckDifferentSentenceConstructions:
    """Tests for check_different_sentence_constructions function."""

    def test_returns_list(self, nlp_model):
        """Test that function returns a list."""
        doc = nlp_model("The filter is clean. The pump is leaky.")
        issues = check_different_sentence_constructions(doc)
        assert isinstance(issues, list)


class TestCheckWordForWordReplacement:
    """Tests for check_word_for_word_replacement function."""

    def test_returns_list(self, nlp_model):
        """Test that function returns a list."""
        doc = nlp_model("The filter is clean. The filter is dry.")
        issues = check_word_for_word_replacement(doc)
        assert isinstance(issues, list)

    def test_different_words(self, nlp_model):
        """Test with different words."""
        doc = nlp_model("The filter is clean. The pump is dry.")
        issues = check_word_for_word_replacement(doc)
        assert isinstance(issues, list)


class TestCheckNonApprovedWords:
    """Tests for check_non_approved_words function."""

    def test_returns_list(self, nlp_model):
        """Test that function returns a list."""
        doc = nlp_model("The bollocks is broken.")
        issues = check_non_approved_words(doc)
        assert isinstance(issues, list)

    def test_normal_text(self, nlp_model):
        """Test with normal text."""
        doc = nlp_model("Check the filter.")
        issues = check_non_approved_words(doc)
        assert isinstance(issues, list)

    def test_self_mapping_entry_is_ignored(self, nlp_model, monkeypatch):
        """A word mapped to itself must not raise an issue.

        The message would read "Use 'test' instead of 'test'".
        """
        import stelint.glossary as glossary

        monkeypatch.setattr(glossary, "NON_APPROVED_WORDS", {"test": "test"})
        doc = nlp_model("Do a functional test of the pump.")
        issues = check_non_approved_words(doc)
        assert issues == []

    def test_legitimate_replacement_still_flagged(self, nlp_model, monkeypatch):
        """The self-mapping guard must not suppress real entries."""
        import stelint.glossary as glossary

        monkeypatch.setattr(glossary, "NON_APPROVED_WORDS", {"test": "test", "leverage": "use"})
        doc = nlp_model("Do a functional test of the pump. Leverage the data.")
        issues = check_non_approved_words(doc)
        assert len(issues) == 1
        assert "leverage" in issues[0]["message"]
