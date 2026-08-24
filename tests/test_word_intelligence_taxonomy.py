"""Taxonomy tests: canonicalization from realistic master-bank fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.taxonomy import (
    STANDARD_BOOK_WORDS,
    TopicTaxonomy,
    jaccard,
)

BANK = {
    "topics": {
        "Gardening": ["SEED", "SOIL", "TROWEL"],
        "Gardening & Garden Life": ["SEED", "SOIL", "TROWEL"],
        "Baking & Food": ["FLOUR", "OVEN", "WHISK"],
        "Baking and Food": ["FLOUR", "OVEN", "WHISK"],
        "Christmas": ["SLEIGH", "ORNAMENT"],
        "Christmas and Winter": ["SLEIGH", "ORNAMENT"],
        "Dog Breeds": ["BEAGLE", "POODLE"],
        "Birdwatching": ["WARBLER", "BINOCULARS"],
        "Weather and Climate": ["CIRRUS", "FRONT"],
        "World War II History": ["SPITFIRE", "LIBERATOR"],
    },
    "topic_to_family": {
        "Gardening": "Animals & Nature",
        "Gardening & Garden Life": "Animals & Nature",
        "Baking & Food": "Home & Wellbeing",
        "Baking and Food": "Home & Wellbeing",
        "Christmas": "Holidays & Seasons",
        "Christmas and Winter": "Holidays & Seasons",
        "Dog Breeds": "Animals & Nature",
        "Birdwatching": "Animals & Nature",
        "Weather and Climate": "General & Flexible",
        "World War II History": "History, Faith & Culture",
    },
    "topic_packs": {
        "Garden, Flowers & Growing Things": ["Gardening", "Gardening & Garden Life"],
        "Christmas, Winter & Cozy Traditions": ["Christmas", "Christmas and Winter"],
    },
}




def build():
    return TopicTaxonomy.from_master_bank(BANK)


class TestCanonicalization:
    def test_ampersand_variants_merge_by_name(self):
        taxo = build()
        assert taxo.resolve("Baking & Food") == taxo.resolve("Baking and Food")

    def test_identical_content_merges_despite_different_names(self):
        taxo = build()
        assert taxo.resolve("Christmas") == taxo.resolve("Christmas and Winter")
        assert taxo.resolve("Gardening") == taxo.resolve("Gardening & Garden Life")

    def test_alias_lookup_is_symmetric(self):
        taxo = build()
        cid = taxo.resolve("Gardening")
        topic = taxo.topics[cid]
        assert set(topic.aliases) == {"Gardening", "Gardening & Garden Life"}

    def test_distinct_topics_stay_distinct(self):
        taxo = build()
        assert taxo.resolve("Dog Breeds") != taxo.resolve("Birdwatching")
        assert taxo.resolve("World War II History") != taxo.resolve("Birdwatching")

    def test_display_name_prefers_friendly_form(self):
        taxo = build()
        cid = taxo.resolve("Gardening & Garden Life")
        assert taxo.topics[cid].display_name == "Gardening"

    def test_word_union_and_examples(self):
        taxo = build()
        cid = taxo.resolve("Baking and Food")
        assert taxo.trusted_words[cid] == {"FLOUR", "OVEN", "WHISK"}
        assert "FLOUR" in taxo.topics[cid].example_words


class TestMetadata:
    def test_family_from_votes(self):
        taxo = build()
        assert taxo.topics[taxo.resolve("Christmas")].family == "Holidays & Seasons"

    def test_pack_membership_recorded(self):
        taxo = build()
        packs = taxo.topics[taxo.resolve("Gardening")].packs
        assert "Garden, Flowers & Growing Things" in packs

    def test_targets_follow_book_rules(self):
        taxo = build()
        assert taxo.topics[taxo.resolve("Birdwatching")].min_vocabulary_target == STANDARD_BOOK_WORDS
        assert taxo.topics[taxo.resolve("Birdwatching")].signature_target == 1200

    def test_provenance_lists_raw_keys(self):
        taxo = build()
        prov = taxo.topics[taxo.resolve("Gardening")].provenance
        assert any("master_bank:Gardening" == p for p in prov)


class TestOverrides:
    def test_related_pairs_are_bidirectional(self):
        taxo = TopicTaxonomy.from_master_bank(BANK, {
            "related_pairs": [{"a": "Birdwatching", "b": "Dog Breeds"}],
        })
        a, b = taxo.resolve("Birdwatching"), taxo.resolve("Dog Breeds")
        assert b in taxo.topics[a].related and a in taxo.topics[b].related

    def test_excluded_pairs_block_relation_closure(self):
        taxo = TopicTaxonomy.from_master_bank(BANK, {
            "related_pairs": [{"a": "Birdwatching", "b": "Dog Breeds"}],
            "excluded_pairs": [{"a": "Birdwatching", "b": "Dog Breeds"}],
        })
        a = taxo.resolve("Birdwatching")
        assert taxo.resolve("Dog Breeds") not in taxo.related_closure(a)

    def test_subtopics_via_overrides(self):
        taxo = TopicTaxonomy.from_master_bank(BANK, {
            "subtopics": {"Holidays & Seasons": []},  # family is not a topic; ignored
        })
        taxo2 = TopicTaxonomy.from_master_bank(BANK, {
            "subtopics": {"Gardening": ["BIRDWATCHING"]},
        })
        parent = taxo2.resolve("Gardening")
        assert taxo2.resolve("Birdwatching") in taxo2.topics[parent].children

    def test_descriptions_applied(self):
        taxo = TopicTaxonomy.from_master_bank(BANK, {
            "descriptions": {"Gardening": "Growing things for joy."},
        })
        assert taxo.get("Gardening").description == "Growing things for joy."


class TestResolution:
    def test_resolve_accepts_slug_display_and_alias(self):
        taxo = build()
        cid = taxo.resolve("Dog Breeds")
        assert taxo.resolve(cid) == cid
        assert taxo.resolve(taxo.topics[cid].display_name) == cid

    def test_resolve_unknown_returns_none(self):
        assert build().resolve("Atlantis Deep Sea Vault") is None
        assert build().resolve("") is None


class TestMergeCandidates:
    def test_near_duplicates_surfaced_not_merged(self):
        # BIRDWATCHING vs DOG BREEDS share nothing; craft partial overlap via overrides bank
        bank = {
            "topics": {
                "Alpha Topic": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
                "Alpha Topic Two": ["A", "B", "C", "D", "E", "F", "G", "H", "K", "L"],
                "Unrelated": ["M"],
            },
            "topic_to_family": {},
            "topic_packs": {},
        }
        taxo = TopicTaxonomy.from_master_bank(bank)
        pairs = {(m["a"], m["b"]) for m in taxo.merge_candidates}
        assert ("Alpha Topic", "Alpha Topic Two") in pairs
        # but they are NOT aliased (content differs)
        assert taxo.resolve("Alpha Topic") != taxo.resolve("Alpha Topic Two")


class TestSerialization:
    def test_round_trip_dict(self):
        taxo = build()
        data = taxo.to_dict()
        assert data["summary"]["canonical_topics"] == len(taxo.topics)
        sample = data["topics"][0]
        for key in ("topic_id", "display_name", "aliases", "trusted_word_count"):
            assert key in sample


def test_jaccard_basics():
    assert jaccard({"a"}, {"a"}) == 1.0
    assert jaccard(set(), set()) == 0.0
    assert abs(jaccard({"a", "b"}, {"b", "c"}) - 1 / 3) < 1e-9