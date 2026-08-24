"""Normalization pipeline tests: comparison keys without destroyed meaning."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.normalization import (
    are_variants,
    clean_surface,
    looks_like_acronym,
    make_record,
    normalize,
    singular_candidates,
    split_tokens,
    variant_group_key,
)


class TestCleanSurface:
    def test_uppercase_and_strip(self):
        assert clean_surface("  garden ") == "GARDEN"

    def test_phrases_lose_spaces_project_convention(self):
        assert normalize("National Park") == "NATIONALPARK"
        assert normalize("hot dog") == "HOTDOG"

    def test_punctuation_removed_letters_kept(self):
        assert normalize("U.S.A.") == "USA"
        assert normalize("rock-n-roll") == "ROCKNROLL"
        assert normalize("o'clock") == "OCLOCK"

    def test_hotdog_is_not_dog(self):
        assert normalize("HOT DOG") != normalize("DOG")

    def test_apple_pie_does_not_collapse_to_apple(self):
        assert normalize("APPLE PIE") != normalize("APPLE")

    def test_empty_and_none_safe(self):
        assert normalize("") == ""
        assert normalize(None) == ""


class TestTokens:
    def test_known_compound_splits(self):
        assert split_tokens("CHOCOLATECAKE") == ("CHOCOLATE", "CAKE")
        assert split_tokens("NATIONALPARK") == ("NATIONAL", "PARK")

    def test_unknown_word_single_token(self):
        assert split_tokens("BRISKET") == ("BRISKET",)

    def test_record_is_phrase(self):
        rec = make_record("Ice Cream")
        assert rec.is_phrase
        assert rec.normalized == "ICECREAM"

    def test_display_prefers_known_form(self):
        rec = make_record("NATIONALPARK", known_display="National Park")
        assert rec.display == "National Park"

    def test_display_without_history_does_not_invent_spacing(self):
        rec = make_record("NATIONALPARK")
        assert rec.display == "NATIONALPARK"


class TestPlurals:
    def test_regular_plural(self):
        assert singular_candidates("DOGS") == ("DOG",)

    def test_ies(self):
        assert "PUPPY" in singular_candidates("PUPPIES")

    def test_ves(self):
        cands = singular_candidates("WOLVES")
        assert "WOLF" in cands and "WOLFE" in cands

    def test_es_after_sibilant(self):
        assert "BATCH" in singular_candidates("BATCHES")
        assert "BOX" in singular_candidates("BOXES")

    def test_ss_never_stripped(self):
        assert singular_candidates("BOSS") == ()
        assert singular_candidates("IRIS") == ()

    def test_short_words_ignored(self):
        assert singular_candidates("ITS") == ()


class TestVariants:
    def test_bbq_group(self):
        assert variant_group_key("BBQ") == variant_group_key("BARBECUE")
        assert are_variants("BARBEQUE", "BARBECUE")

    def test_distinct_words_not_variants(self):
        assert not are_variants("DOG", "CAT")
        assert variant_group_key("BRISKET") == "BRISKET"


class TestAcronyms:
    def test_perioded_initialism(self):
        assert looks_like_acronym("USA", original="U.S.A.")

    def test_plain_short_caps(self):
        assert looks_like_acronym("FBI")

    def test_long_word_not_acronym(self):
        assert not looks_like_acronym("GARDENING")
