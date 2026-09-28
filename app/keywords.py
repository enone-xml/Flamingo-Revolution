"""Keyword prefilter, so only likely-relevant articles are sent to the AI.

Matching ignores case and diacritics, so "Zvërnec", "ZVERNEC" and "zvernec"
all match. Edit the lists below to widen or narrow the filter.
"""
import re
import unicodedata

# Match anywhere, for any source.
STRONG_TERMS = [
    "flamingo",               # Flamingo Revolution, Revolucioni i Flamingove, flamingot
    "zvernec",
    "sazan",
    "vjosa-narta", "vjose-narte", "vjosa narta", "narta lagoon", "laguna e nartes",
    "pishe poro",
    "edi rama",
    "rama government", "rama's government", "qeveria rama", "qeveria e rames",
    "kushner",                # the Zvërnec/Sazan resort developer
]

# Match only for Albanian outlets (country: AL), where the context is implied.
LOCAL_TERMS = [
    "protest",                                      # protesta, protestues, protest
    "revolucion",
    "qeveri",                                       # qeveria, qeverise...
    "opozit",                                       # opozita, opozites
    "korrupsion", "spak",
    "ambientalist",
]

# Whole words only, for Albanian outlets ("rama" must not match "ramazan").
LOCAL_WORDS = ["rama", "ramen", "rames", "ramet"]

# International outlets must mention Albania together with a topic word.
ALBANIA_TERMS = ["albania", "albanian", "tirana", "shqiperi"]
TOPIC_TERMS = [
    "protest", "government", "prime minister", "police", "arrest",
    "opposition", "corruption", "resort", "environment", "lagoon", "election",
]


def normalize(text: str) -> str:
    """Lowercase and strip diacritics: 'Zvërnec Çelësi' -> 'zvernec celesi'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def _has_word(text: str, words: list[str]) -> bool:
    return any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text) for w in words)


def _has(text: str, terms: list[str]) -> bool:
    # Terms match at the start of a word, so "protest" matches "protesta"
    # but "spak" does not match inside another word.
    return any(re.search(r"(?<![a-z])" + re.escape(t), text) for t in terms)


def is_candidate(title: str, snippet: str, country: str) -> bool:
    text = normalize(f"{title} {snippet}")
    if _has(text, STRONG_TERMS):
        return True
    if country == "AL":
        return _has(text, LOCAL_TERMS) or _has_word(text, LOCAL_WORDS)
    return _has(text, ALBANIA_TERMS) and _has(text, TOPIC_TERMS)
