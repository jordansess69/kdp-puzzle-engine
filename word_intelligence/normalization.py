"""Canonical word/phrase normalization for the Word Intelligence system.

One pipeline, used everywhere, that NEVER destroys meaningful distinctions:

- ``normalize``          -> stable comparison key (matches the existing master
                            bank convention of space-free uppercase A-Z forms,
                            e.g. "National Park" -> "NATIONALPARK").
- ``display_form``       -> human-facing presentation (original where known).
- ``tokens``             -> meaningful phrase parts for signal matching
                            ("CHOCOLATECAKE" -> ["CHOCOLATE", "CAKE"]).
- variant/plural helpers -> candidate relationships for classification only;
                            storage entries are never auto-merged (BBQ /
                            BARBECUE / BARBEQUE stay distinct records linked
                            as aliases).

Design rules from the mission brief:
  HOT DOG   is not DOG            (token sets differ)
  APPLE PIE does not collapse to APPLE
  U.S.A.    normalizes to USA     (punctuation removed, letters kept)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_ALLOWED = re.compile(r"[^A-Z]")

# Deterministic spelling-variant groups (classification hints only).
# Each group lists surface spellings considered interchangeable when
# MATCHING; the stored records remain separate unless a human merges them.
SPELLING_VARIANT_GROUPS: tuple[tuple[str, ...], ...] = (
    ("BARBECUE", "BARBEQUE", "BBQ"),
    ("GRAY", "GREY"),
    ("COLOR", "COLOUR"),
    ("FLAVOR", "FLAVOUR"),
    ("HUMOR", "HUMOUR"),
    ("FAVOR", "FAVOUR"),
    ("LABOR", "LABOUR"),
    ("BEHAVIOR", "BEHAVIOUR"),
    ("CANCELED", "CANCELLED"),
    ("TRAVELING", "TRAVELLING"),
    ("JUDGMENT", "JUDGEMENT"),
)

# Very common contraction/apostrophe expansions so O'CLOCK style tokens keep
# their meaning after punctuation stripping.
_APOSTROPHE_EXPANSIONS = {
    "OCLOCK": "OCLOCK",  # kept as-is; documented no-op for clarity
}

_VARIANT_LOOKUP: dict[str, str] = {}
for _group in SPELLING_VARIANT_GROUPS:
    _canonical = max(_group, key=len)  # longest spelling is the group key
    for _spelling in _group:
        _VARIANT_LOOKUP[_spelling] = _canonical


@dataclass(frozen=True)
class NormalizedWord:
    """Everything the intelligence layer needs about one surface form."""

    original: str
    normalized: str
    display: str
    tokens: tuple[str, ...] = field(default=())

    @property
    def is_phrase(self) -> bool:
        return len(self.tokens) > 1

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "normalized": self.normalized,
            "display": self.display,
            "tokens": list(self.tokens),
        }


def clean_surface(raw: str) -> str:
    """Uppercase + strip everything except A-Z (existing project convention).

    Hyphens, apostrophes, periods, commas and whitespace all collapse away,
    mirroring how the master bank stores phrases ("NATIONALPARK").
    """
    return _ALLOWED.sub("", str(raw or "").upper())


def split_tokens(normalized: str) -> tuple[str, ...]:
    """Recover meaningful tokens from a space-free normalized form.

    Compound words in this project were stored without spaces, so token
    recovery uses a curated compound-split table plus vowel-group heuristics.
    Unknown single-token words simply yield themselves.
    """
    if not normalized:
        return ()
    known = COMPOUND_SPLITS.get(normalized)
    if known:
        return tuple(known)
    return (normalized,)


def normalize(raw: str) -> str:
    """The one comparison key for words and topic names alike."""
    return clean_surface(raw)


def display_form(raw: str, known_display: str | None = None) -> str:
    """Prefer a previously recorded human form; else title-case the phrase.

    "NATIONALPARK" with no history stays "NATIONALPARK" - we never invent
    spacing that might be wrong.
    """
    text = str(known_display or "").strip()
    if text:
        return text
    cleaned = clean_surface(raw)
    return cleaned


def make_record(raw: str, known_display: str | None = None) -> NormalizedWord:
    """Build the full normalization record for one surface string."""
    norm = normalize(raw)
    return NormalizedWord(
        original=str(raw or ""),
        normalized=norm,
        display=display_form(raw, known_display),
        tokens=split_tokens(norm),
    )


def singular_candidates(token: str) -> tuple[str, ...]:
    """Plural->singular candidates for MATCHING only (never storage merges).

    Deterministic English-ish rules with conservative guards:
    "DOGS"->"DOG", "BATCHES"->"BATCH", "WOLVES"->"WOLF".
    Returns () when the token is already singular-looking.
    """
    if len(token) < 4 or not token.endswith("S"):
        return ()
    out: list[str] = []
    if token.endswith("IES") and len(token) >= 5:
        out.append(token[:-3] + "Y")
    if token.endswith("VES") and len(token) >= 5:
        out.append(token[:-3] + "F")
        out.append(token[:-3] + "FE")
    if token.endswith("SES") or token.endswith("XES") or token.endswith("ZES") \
            or token.endswith("CHES") or token.endswith("SHES"):
        out.append(token[:-2])
    if token.endswith("SS") or token.endswith("US") or token.endswith("IS"):
        pass  # "BOSS"/"BUS"/"IRIS"-like; plural stripping would corrupt
    else:
        out.append(token[:-1])
    # drop identity and junk results
    return tuple(dict.fromkeys(c for c in out if len(c) >= 3 and c != token))


def variant_group_key(token: str) -> str:
    """Group key for spelling variants (BBQ/BARBECUE share a key)."""
    return _VARIANT_LOOKUP.get(token, token)


def are_variants(a: str, b: str) -> bool:
    """True when two normalized forms are spelling variants of one concept."""
    ka, kb = variant_group_key(a), variant_group_key(b)
    return ka == kb and a != b


def looks_like_acronym(token: str, original: str | None = None) -> bool:
    """USA/U.S.A./FBI-style short all-caps initialisms."""
    if original:
        stripped = re.sub(r"[^A-Za-z.]", "", original)
        if "." in stripped and stripped.replace(".", "").isupper():
            return len(stripped.replace(".", "")) <= 5
    return len(token) <= 5 and _ALLOWED.sub("", token) == token


# Curated compound splits for phrases already stored space-free.
# Only entries that matter for signal quality live here; unknown compounds
# degrade gracefully to single tokens.
COMPOUND_SPLITS: dict[str, tuple[str, ...]] = {
    "NATIONALPARK": ("NATIONAL", "PARK"),
    "NATIONALMONUMENT": ("NATIONAL", "MONUMENT"),
    "GREATLAKES": ("GREAT", "LAKE"),  # note: LAKE not LAKES for token signals
    "ICECREAM": ("ICE", "CREAM"),
    "HOTDOG": ("HOT", "DOG"),
    "APPLEPIE": ("APPLE", "PIE"),
    "CHOCOLATECAKE": ("CHOCOLATE", "CAKE"),
    "UNITEDSTATES": ("UNITED", "STATES"),
    "ROADCAR": ("ROAD", "CAR"),
    "MOUNTAINBIKE": ("MOUNTAIN", "BIKE"),
    "BIRDWATCHING": ("BIRD", "WATCHING"),
    "BIRDHOUSE": ("BIRD", "HOUSE"),
    "BIRDSEED": ("BIRD", "SEED"),
    "BIRDFEEDER": ("BIRD", "FEEDER"),
    "SUNFLOWER": ("SUN", "FLOWER"),
    "FLOWERPOT": ("FLOWER", "POT"),
    "GARDENHOSE": ("GARDEN", "HOSE"),
    "WHEELBARROW": ("WHEEL", "BARROW"),
    "RAINGAUGE": ("RAIN", "GAUGE"),
    "RAINBOW": ("RAIN", "BOW"),
    "SNOWMAN": ("SNOW", "MAN"),
    "SNOWFLAKE": ("SNOW", "FLAKE"),
    "FIREPLACE": ("FIRE", "PLACE"),
    "FIREPIT": ("FIRE", "PIT"),
    "CAMPGROUND": ("CAMP", "GROUND"),
    "BACKPACK": ("BACK", "PACK"),
    "TRAILHEAD": ("TRAIL", "HEAD"),
    "WILDLIFE": ("WILD", "LIFE"),
    "MOONLIGHT": ("MOON", "LIGHT"),
    "STARFISH": ("STAR", "FISH"),
    "JELLYFISH": ("JELLY", "FISH"),
    "SWORDFISH": ("SWORD", "FISH"),
    "SEAHORSE": ("SEA", "HORSE"),
    "SANDCASTLE": ("SAND", "CASTLE"),
    "SURFBOARD": ("SURF", "BOARD"),
    "SKATEBOARD": ("SKATE", "BOARD"),
    "KEYBOARD": ("KEY", "BOARD"),
    "FOOTBALL": ("FOOT", "BALL"),
    "BASKETBALL": ("BASKET", "BALL"),
    "BASEBALL": ("BASE", "BALL"),
    "VOLLEYBALL": ("VOLLEY", "BALL"),
    "HOMEWORK": ("HOME", "WORK"),
    "NOTEBOOK": ("NOTE", "BOOK"),
    "NEWSPAPER": ("NEWS", "PAPER"),
    "BIRTHDAY": ("BIRTH", "DAY"),
    "WEEKEND": ("WEEK", "END"),
    "GRANDCANYON": ("GRAND", "CANYON"),
    "YELLOWSTONE": ("YELLOW", "STONE"),
    "SPACESHUTTLE": ("SPACE", "SHUTTLE"),
    "SOLARSYSTEM": ("SOLAR", "SYSTEM"),
    "MILKYWAY": ("MILKY", "WAY"),
    "NORTHERNLIGHTS": ("NORTHERN", "LIGHTS"),
}
