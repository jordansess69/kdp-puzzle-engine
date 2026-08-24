"""Canonical Topic Taxonomy built from the ACTUAL project data.

The master bank stores 78 raw topic keys, many of which are naming variants
of the same real-world topic ("Gardening", "Gardening & Garden Life",
"Gardening and Garden Life", ...).  The taxonomy layer gives every concept:

    canonical_topic_id      stable slug, e.g. "gardening"
    display_name            best human-facing name among the aliases
    aliases                 every master-bank key that means this topic
    family / pack membership, related + excluded topics,
    description, example words, vocabulary targets,
    current trusted word count and provenance.

Building this layer NEVER modifies the master bank - it is a read-model.
Content-identical raw topics become aliases automatically (with evidence);
near-identical ones are surfaced as merge candidates for humans.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .normalization import clean_surface

# Book-size targets mirror TOPIC_LIBRARY_READINESS.json conventions.
STANDARD_BOOK_WORDS = 576   # 48 puzzles x 12 words
SIGNATURE_BOOK_WORDS = 1200  # signature editions


@dataclass
class TopicDef:
    """One canonical topic."""

    topic_id: str
    display_name: str
    aliases: list[str] = field(default_factory=list)       # raw master-bank keys
    family: str = ""
    packs: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)        # canonical ids
    excluded: list[str] = field(default_factory=list)       # canonical ids
    children: list[str] = field(default_factory=list)       # canonical subtopic ids
    description: str = ""
    example_words: list[str] = field(default_factory=list)
    min_vocabulary_target: int = STANDARD_BOOK_WORDS
    signature_target: int = SIGNATURE_BOOK_WORDS
    provenance: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return int(getattr(self, "_trusted_count", 0))

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "display_name": self.display_name,
            "aliases": list(self.aliases),
            "family": self.family,
            "packs": list(self.packs),
            "related": list(self.related),
            "excluded": list(self.excluded),
            "children": list(self.children),
            "description": self.description,
            "example_words": list(self.example_words),
            "min_vocabulary_target": self.min_vocabulary_target,
            "signature_target": self.signature_target,
            "provenance": list(self.provenance),
            "trusted_word_count": self.word_count,
        }


_NAME_TOKEN_SPLIT = re.compile(r"[^A-Za-z]+")
_NAME_STOPWORDS = frozenset({"AND", "THE", "OF", "FOR", "A", "AN", "IN"})


def _name_tokens_in_order(raw_name: str) -> list[str]:
    """Ordered meaningful tokens of a topic name ('Dog Breeds' -> [DOG, BREEDS])."""
    raw = re.sub(r"&", " and ", str(raw_name or ""))
    seen: list[str] = []
    for tok in _NAME_TOKEN_SPLIT.split(raw):
        tok = tok.upper()
        if tok and tok not in _NAME_STOPWORDS and tok not in seen:
            seen.append(tok)
    return seen


def _name_key(raw_name: str) -> frozenset[str]:
    return frozenset(_name_tokens_in_order(raw_name))


def canonical_slug(tokens: list[str] | frozenset[str]) -> str:
    ordered = list(dict.fromkeys(tokens)) if not isinstance(tokens, frozenset) else sorted(tokens)
    return "_".join(ordered).casefold()


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class TopicTaxonomy:
    """Read-model over the master bank's topics/families/packs."""

    def __init__(self) -> None:
        self.topics: dict[str, TopicDef] = {}
        self.alias_to_id: dict[str, str] = {}     # raw key -> canonical id
        self.families: dict[str, list[str]] = {}
        self.merge_candidates: list[dict] = []     # near-duplicates for humans
        self.trusted_words: dict[str, set[str]] = {}  # canonical id -> words
        self._raw_words_by_key: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    @classmethod
    def from_master_bank(cls, bank: dict, overrides: dict | None = None) -> "TopicTaxonomy":
        taxo = cls()
        topics = bank.get("topics") or {}
        t2f = bank.get("topic_to_family") or {}
        packs = bank.get("topic_packs") or {}
        words_by_key = {
            key: {clean_surface(w) for w in members}
            for key, members in topics.items()
        }
        taxo._raw_words_by_key = words_by_key

        # Group raw keys into concepts: exact token-set name match first,
        # then identical content (word sets) as strong evidence of sameness.
        by_name: dict[frozenset[str], list[str]] = {}
        for key in topics:
            by_name.setdefault(_name_key(key), []).append(key)

        concepts: list[list[str]] = []
        key_to_concept: dict[str, list[str]] = {}
        for group in by_name.values():
            concept = list(group)
            concepts.append(concept)
            for key in group:
                key_to_concept[key] = concept

        # Content-identical CONCEPTS are the same real-world topic even when
        # their names differ ("Christmas" vs "Christmas and Winter" carrying
        # identical word lists). Union them; empty topics never merge.
        changed = True
        while changed:
            changed = False
            for i in range(len(concepts)):
                if not concepts[i]:
                    continue
                for j in range(i + 1, len(concepts)):
                    if not concepts[j]:
                        continue
                    wi = words_by_key[concepts[i][0]]
                    wj = words_by_key[concepts[j][0]]
                    if wi and wi == wj:
                        concepts[i].extend(concepts[j])
                        for key in concepts[j]:
                            key_to_concept[key] = concepts[i]
                        concepts[j] = []
                        changed = True
        concepts = [c for c in concepts if c]

        # Near-duplicate reporting (not auto-merged).
        seen_pairs: set[tuple[str, str]] = set()
        for i, a in enumerate(topics):
            for b in list(topics)[i + 1:]:
                if a in key_to_concept[b] or (a, b) in seen_pairs:
                    continue
                sim = jaccard(words_by_key[a], words_by_key[b])
                if 0.60 <= sim < 1.0:
                    pair = tuple(sorted((a, b)))
                    seen_pairs.add(pair)
                    taxo.merge_candidates.append({
                        "a": pair[0], "b": pair[1],
                        "jaccard": round(sim, 3),
                        "shared_words": len(words_by_key[a] & words_by_key[b]),
                    })

        # Pack membership per raw key -> concept.
        pack_of_key: dict[str, list[str]] = {}
        for pack_name, members in packs.items():
            for key in members or []:
                pack_of_key.setdefault(key, []).append(pack_name)

        for concept in concepts:
            words: set[str] = set()
            provenance: list[str] = []
            for key in sorted(concept):
                words |= words_by_key[key]
                provenance.append(f"master_bank:{key}")
            primary = cls._pick_display_name(concept)
            slug = canonical_slug(_name_tokens_in_order(primary))
            # Guarantee uniqueness even after aggressive merging.
            base_slug = slug
            n = 2
            while slug in taxo.topics:
                slug = f"{base_slug}_{n}"
                n += 1
            families_votes: dict[str, int] = {}
            for key in concept:
                fam = t2f.get(key, "")
                if fam:
                    families_votes[fam] = families_votes.get(fam, 0) + 1
            family = max(families_votes, key=lambda f: (families_votes[f], f)) if families_votes else ""
            packs_for_concept = sorted({p for key in concept for p in pack_of_key.get(key, [])})
            example = sorted(words)[:12]
            taxo.topics[slug] = TopicDef(
                topic_id=slug,
                display_name=primary,
                aliases=sorted(concept),
                family=family,
                packs=packs_for_concept,
                description="",
                example_words=example,
                provenance=provenance,
            )
            for key in concept:
                taxo.alias_to_id[key] = slug
            taxo.trusted_words[slug] = words

        for slug, topic in taxo.topics.items():
            taxo.families.setdefault(topic.family, []).append(slug)

        taxo.apply_overrides(overrides or {})
        return taxo

    @staticmethod
    def _pick_display_name(concept: list[str]) -> str:
        """Prefer the friendliest existing name: shortest non-'Signature' one."""
        candidates = [c for c in concept if "signature" not in c.casefold()]
        pool = candidates or concept
        return min(pool, key=lambda c: (len(c), c))

    def apply_overrides(self, overrides: dict) -> None:
        """Curated additions: descriptions, relations, exclusions, subtopics."""
        for entry in overrides.get("related_pairs", []):
            a, b = self.resolve(entry.get("a", "")), self.resolve(entry.get("b", ""))
            if a and b and a != b:
                for x, y in ((a, b), (b, a)):
                    if y not in self.topics[x].related:
                        self.topics[x].related.append(y)
        for entry in overrides.get("excluded_pairs", []):
            a, b = self.resolve(entry.get("a", "")), self.resolve(entry.get("b", ""))
            if a and b and a != b:
                for x, y in ((a, b), (b, a)):
                    if y not in self.topics[x].excluded:
                        self.topics[x].excluded.append(y)
                        if x not in self.topics[y].related:
                            pass  # exclusion wins; no silent relation added
        for topic_id, subs in (overrides.get("subtopics") or {}).items():
            parent = self.resolve(topic_id)
            if not parent:
                continue
            for child in subs:
                child_id = self.resolve(child)
                if child_id and child_id != parent and child_id not in self.topics[parent].children:
                    self.topics[parent].children.append(child_id)
        for topic_id, text in (overrides.get("descriptions") or {}).items():
            t = self.resolve(topic_id)
            if t:
                self.topics[t].description = str(text)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def resolve(self, raw_name: str) -> str | None:
        """Raw master-bank key OR canonical display/slug -> canonical id."""
        if not raw_name:
            return None
        raw = str(raw_name)
        if raw in self.alias_to_id:
            return self.alias_to_id[raw]
        cleaned = clean_surface(raw)
        for slug, topic in self.topics.items():
            if slug == raw.casefold() or clean_surface(topic.display_name) == cleaned:
                return slug
            for alias in topic.aliases:
                if clean_surface(alias) == cleaned:
                    return slug
        return None

    def get(self, raw_or_id: str) -> TopicDef | None:
        cid = self.resolve(raw_or_id)
        return self.topics.get(cid) if cid else None

    def display_name(self, raw_or_id: str) -> str:
        cid = self.resolve(raw_or_id) if raw_or_id in self.topics else raw_or_id
        topic = self.topics.get(cid or "")
        return topic.display_name if topic else (raw_or_id or "")

    def related_closure(self, topic_id: str, hops: int = 1) -> set[str]:
        """Canonical ids within `hops` relation steps (exclusions never cross)."""
        start = self.resolve(topic_id)
        if not start:
            return set()
        seen = {start}
        frontier = {start}
        for _ in range(hops):
            nxt: set[str] = set()
            for tid in frontier:
                for rel in self.topics[tid].related:
                    if rel not in seen and start not in self.topics[rel].excluded:
                        nxt.add(rel)
            seen |= nxt
            frontier = nxt
        seen.discard(start)
        return seen

    def summary(self) -> dict:
        return {
            "canonical_topics": len(self.topics),
            "raw_topic_keys": len(self.alias_to_id),
            "families": {f: len(m) for f, m in sorted(self.families.items())},
            "merge_candidates": len(self.merge_candidates),
        }

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "topics": [t.to_dict() for t in
                       sorted(self.topics.values(), key=lambda t: t.display_name.casefold())],
            "merge_candidates": sorted(
                self.merge_candidates, key=lambda m: (-m["jaccard"], m["a"])),
        }


def load_overrides(path) -> dict:
    """Optional curated overrides file; missing file is normal."""
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
