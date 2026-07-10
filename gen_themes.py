#!/usr/bin/env python3
"""
gen_themes.py — the catalog multiplier. Local Ollama (free) fills word lists for a new book.

You give a spec (title/subtitle/author/palette + a list of sub-theme NAMES). Ollama generates
the words for each theme; this script validates + cleans them (uppercase, letters only,
length 3-13, deduped). Output is a themes JSON ready for wordsearch.py.

    /usr/bin/python3 gen_themes.py --spec specs/food.json --out themes/food.json

⚠️ QUALITY WARNING: the free local model (qwen2.5:3b) is NOT reliable for factual word lists.
It hallucinates fake words (e.g. "SNOUFFLEDOG", "FOGLIASSI") and miscategorizes. This tool is
a DRAFT skeleton only — every list MUST be reviewed and corrected by hand, or run against a
stronger model (e.g. a free Gemini/Groq key via the llm shim). For publishable quality, the
nature/food/animals themes JSON were hand-curated, not taken raw from this tool.
Runs on /usr/bin/python3 (stdlib only). Needs Ollama running (open -a Ollama).
"""
import argparse, json, os, re, sys, urllib.request

OLLAMA, MODEL = "http://127.0.0.1:11434/api/generate", "qwen2.5:3b"
MINLEN, MAXLEN, WANT, MINKEEP = 3, 13, 14, 10


def ask(theme):
    prompt = (
        f"List 18 common English words related to the topic: {theme}.\n"
        "Strict rules: one word per line; UPPERCASE; letters A-Z only; no spaces, hyphens, "
        f"numbers or phrases; each word {MINLEN} to {MAXLEN} letters; real well-known words; "
        "no duplicates.\nOutput only the list, nothing else."
    )
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.5, "num_predict": 300}}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode()).get("response", "")


def clean(raw):
    out, seen = [], set()
    for line in raw.splitlines():
        w = re.sub(r"[^A-Za-z]", "", line).upper()
        if MINLEN <= len(w) <= MAXLEN and w not in seen:
            seen.add(w)
            out.append(w)
    return out[:WANT]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    spec = json.load(open(a.spec))
    puzzles = []
    for name in spec["themes"]:
        words = []
        for _ in range(2):
            words = clean(ask(name))
            if len(words) >= MINKEEP:
                break
        if len(words) < MINKEEP:
            print(f"  WARN '{name}': only {len(words)} words (kept anyway)", file=sys.stderr)
        puzzles.append({"name": name, "words": words})
        print(f"  {name}: {len(words)} words")

    book = {
        "title": spec["title"],
        "subtitle": spec.get("subtitle", ""),
        "author": spec.get("author", ""),
        "palette": spec.get("palette", "nature"),
        "puzzles": puzzles,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(book, open(a.out, "w"), indent=2)
    print(f"DONE -> {a.out}  ({len(puzzles)} puzzles)")


if __name__ == "__main__":
    main()
