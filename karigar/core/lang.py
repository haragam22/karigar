"""Reply-language detection: mirror the request (decisions.md "Product choices from the user").

Deterministic and tiny on purpose: romanised Hindi function words mark a message as
Hinglish; everything else is English. Numbers, units and job cards stay English either way.
"""
from __future__ import annotations

import re

EN = "en"
HINGLISH = "hinglish"
LANGS = (EN, HINGLISH)

# Words that almost never appear in English sentences.
_STRONG = {
    "hai", "hain", "chahiye", "chaiye", "banana", "banao", "banwana", "bana", "purana", "purani",
    "purane", "mujhe", "aaj", "mera", "meri", "mere", "naya", "nayi", "naye", "kuch", "nahi",
    "nahin", "karna", "karo", "kijiye", "dijiye", "batao", "bataiye", "sona", "sone", "anguthi",
    "angoothi", "kangan", "kada", "hoon", "kitna", "kitne", "uske", "badle", "wala", "wali", "wale",
    "bhav", "bhaav", "sundar", "chhota", "chhoti", "bada", "badi", "humein", "hume", "dena", "do",
}
# Short words that are Hindi in context but could be noise alone.
_WEAK = {"ka", "ki", "ke", "se", "sa", "si", "ek", "aur", "ya", "ko", "kya", "ho", "nani", "dadi"}
_WORD = re.compile(r"[a-z]+")


def detect(text: str) -> str:
    """'hinglish' when the message reads as romanised Hindi, else 'en'."""
    if re.search(r"[\u0900-\u097f]", text):
        return HINGLISH
    words = _WORD.findall(text.lower())
    # An English personal name and the English verb "do" need other Hindi context.
    if "Sona" in text and not any(w in _STRONG - {"sona", "do"} or w in _WEAK for w in words):
        return EN
    strong = sum(w in _STRONG for w in words)
    weak = sum(w in _WEAK for w in words)
    # "do" alone is English ("do you…"); it counts only next to another Hindi word.
    if strong - words.count("do") >= 1 or strong - words.count("do") + weak >= 2:
        return HINGLISH
    return EN
