"""Tests for glossary loading and data validation."""

from stelint.glossary import _REPLACEMENT_CONSTANT_NAMES, _constants, _validate_replacement_mappings


class TestReplacementMappingData:
    """The base data must not contain self-mapping replacement entries."""

    def test_base_data_has_no_self_mapping_replacements(self):
        """No replacement constant may map a word to itself.

        A self-mapping such as NON_APPROVED_WORDS['test'] = 'test'
        produces the meaningless message "Use 'test' instead of 'test'".
        """
        bad = []
        for name in sorted(_REPLACEMENT_CONSTANT_NAMES):
            value = _constants.get(name)
            if not isinstance(value, dict):
                continue
            for key, replacement in value.items():
                if isinstance(key, str) and isinstance(replacement, str) and replacement.strip().lower() == key.strip().lower():
                    bad.append((name, key))
        assert bad == []


class TestValidateReplacementMappings:
    """Load-time validation must warn on self-mapping entries."""

    def test_warns_on_self_mapping(self, capsys):
        _validate_replacement_mappings({"NON_APPROVED_WORDS": {"test": "test"}})
        err = capsys.readouterr().err
        assert "NON_APPROVED_WORDS" in err
        assert "test" in err

    def test_warning_is_case_insensitive(self, capsys):
        _validate_replacement_mappings({"NON_APPROVED_WORDS": {"Test": "test"}})
        err = capsys.readouterr().err
        assert "NON_APPROVED_WORDS" in err

    def test_no_warning_for_valid_replacement(self, capsys):
        _validate_replacement_mappings({"NON_APPROVED_WORDS": {"test": "do a test"}})
        err = capsys.readouterr().err
        assert err == ""

    def test_no_warning_for_non_string_values(self, capsys):
        """Entries without a replacement (None) are a valid data form."""
        _validate_replacement_mappings({"NON_APPROVED_WORDS": {"any": None}})
        err = capsys.readouterr().err
        assert err == ""

    def test_untracked_constants_are_not_warned(self, capsys):
        """CONSISTENT_STYLE_PATTERNS self-mappings are intentional.

        They mark approved compound terms, for example 'nut' -> 'nut'.
        """
        _validate_replacement_mappings({"CONSISTENT_STYLE_PATTERNS": {"nut": "nut"}})
        err = capsys.readouterr().err
        assert err == ""
