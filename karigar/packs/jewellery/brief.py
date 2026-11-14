"""Sakhi at the counter: turn a customer's words (English/Hinglish) into a Brief,
or ask for the blocking fields that are missing (up to three questions in one reply).

Order of work in `analyse`:
1. Detect the reply language (core/lang.py).
2. Out-of-scope pieces (necklace, mangalsutra, anklet, maang tikka) get a scope reply + nearest piece.
3. Draft the fields: LLM JSON validated against `BriefDraft`, repaired once with the
   validation error, else the deterministic regex parser.
4. Ask only for blocking fields (piece, target, ring/bangle size, chain length, new karat,
   old karat); state defaults
   for the rest (metal colour, stone size). Ambiguous style words never trigger a question.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from karigar.core import llm
from karigar.core.lang import EN, detect

from . import messages as M
from . import sizes
from .schema import STYLE_WORDS, Brief, ChainLength, Gem, Karat, Metal, PieceType, style_tags

MAX_QUESTIONS = 3
MAX_INPUT_CHARS = 2000


def inr(x):
    from .pricing import inr as _inr
    return _inr(x)


# First match wins, in this order: "nose ring" is a nose pin; a chain is usually the old gold
# being exchanged, so any other piece named in the same request is the one to make
# ("purani chain se jhumka banana").
PIECE_WORDS = {
    "nosepin": r"\b(nose\s*pins?|nosepins?|nose\s*studs?|nose\s*rings?|nath|nathni|laung|koka)\b",
    "ring": r"\b(ring|rings|anguthi|angoothi|solitaire)\b",
    "bangle": r"\b(bangles?|kada|kara|kangan|chudi|churi|bracelet)\b",
    "pendant": r"\b(pendant|locket)\b",
    "coin": r"\b(coins?|sikka|sikke|sikkay)\b",
    "earring": (r"\b(earrings?|ear\s*rings?|jhumk(?:a|i|e|as|is)|chand\s*bali|chandbalis?|kaan\s*ki\s*bali"
                r"|baali|bali|balis|tops|studs?|ear\s*studs?)\b"),
    "chain": r"\b(chains?)\b",
}
_ANY_PIECE = "|".join(f"(?:{p})" for p in PIECE_WORDS.values())
GEM_WORDS = {
    "diamond": r"\b(diamond|heera|solitaire)\b", "ruby": r"\b(ruby|manik|manikya)\b",
    "emerald": r"\b(emerald|panna)\b", "sapphire": r"\b(sapphire|neelam)\b",
}
OLD_WORDS = r"\b(old|purana|purani|purane|exchange|grandm\w*|nani|dadi|mummy|mom'?s|melt|trade)\b"

# (pattern, English label, nearest supported piece, is a likely old-gold source)
# Earrings, chains, nose pins and coins are in scope since Phase 2.5 (decisions.md 2026-11-13
# "Design catalogue"); necklace sets, mangalsutras, anklets and maang tikkas still are not.
OUT_OF_SCOPE = [
    (r"\b(necklaces?|haar|choker|mangalsutra)\b", "necklaces or mangalsutras", "chain + pendant", True),
    (r"\b(anklets?|payal|paayal|pajeb)\b", "anklets", "bangle", False),
    (r"\b(maang\s*tikka|tikka)\b", "maang tikkas", "pendant", False),
]

# A style word that names a catalogue family, per piece type; first match wins.
# "kada" names the temple kada only when no other bangle look is asked for ("beaded kada").
FAMILY_WORDS: list[tuple[str, str, str]] = [
    ("earring", r"\bchand\s*bali", "earring_chandbali"),
    ("earring", r"\bjhumk(?:a|i|e|as|is)\b", "earring_jhumka"),
    ("earring", r"\b(bali|baali|balis|hoops?)\b", "earring_bali_hoop"),
    ("chain", r"\brope\b", "chain_rope"),
    ("chain", r"\bcurb\b", "chain_curb"),
    ("bangle", r"\b(rope|twisted)\b", "bangle_twisted_rope"),
    ("bangle", r"\btemple\b", "bangle_temple_kada"),
    ("bangle", r"^(?!.*\b(?:beaded|plain|faceted)\b).*\bkada\b", "bangle_temple_kada"),
    ("ring", r"\b(three|3)[\s-]*stones?\b", "ring_three_stone"),
    ("ring", r"\bhalo\b", "ring_halo_solitaire"),
    ("ring", r"\b(butterfly|titli)\b", "ring_butterfly"),
    ("pendant", r"\bhalo\b", "pendant_heart_halo"),
    ("pendant", r"\b(paisley|mango|keri|kairi)\b", "pendant_paisley"),
    ("pendant", r"\b(temple|lotus|kamal)\b", "pendant_temple_lotus"),
    ("coin", r"\b(lotus|kamal)\b", "coin_lotus_10g"),
]
CHAIN_LENGTH = r"(?<!\d)(16|18|20|22|24)\s*(?:\"|''|-?\s*inch(?:es)?\b|in\b|inchi?\b)"


def family_from_text(piece: str | None, t: str) -> str | None:
    """The catalogue family a style word names for this piece, or None. Code only, never the LLM."""
    from .families import CATALOGUE, FAMILIES
    for name in CATALOGUE:
        if name in FAMILIES and FAMILIES[name].piece_type == piece and re.search(rf"\b{re.escape(name)}\b", t):
            return name
    for p, pat, fam in FAMILY_WORDS:
        if p == piece and re.search(pat, t, re.S):
            return fam
    return None

_LIGHTER = r"\b(lighter|halka|halki|halke)\b"

SYSTEM = """You are Sakhi, the counter assistant of an Indian jewellery shop.
Extract the customer's request into one JSON object. Include ONLY keys the customer actually stated; never guess:
piece_type: "ring"|"bangle"|"pendant"|"chain"|"coin"|"earring"|"nosepin"; karat (new piece): 22|18|14; metal: "yellow"|"rose"|"white";
old_gold: {weight_g, karat (24|22|18|14)};
target_weight_g (finished weight, only if they ask for a weight and have no old gold);
budget_inr; gem: "none"|"diamond"|"ruby"|"emerald"|"sapphire"; gem_ct;
ring_size (Indian ring size number 1-30) or ring_inner_d_mm (only if given in mm);
bangle_inner_d_mm (Indian bangle sizes like 2-6 mean 2 6/16 inch inner diameter);
length_in (chain length in inches: 16|18|20|22|24);
style: list of words like lotus, beaded, plain, knife, faceted, floral, traditional, modern.
"22 carat" means karat 22, not gem carats. Return JSON only."""


class OldGoldDraft(BaseModel):
    """No purity field: claimed/tested purity is dropped, even if the LLM sends one (security F9)."""
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    weight_g: float = Field(gt=0, le=500)
    karat: Optional[Literal[24, 22, 18, 14]] = None


class BriefDraft(BaseModel):
    """What was stated, nothing filled in. The LLM output must validate against this.
    inf/NaN are refused (security F7); `style` keeps known tags only (security F8)."""
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    piece_type: Optional[PieceType] = None
    karat: Optional[Karat] = None
    metal: Optional[Metal] = None
    old_gold: Optional[OldGoldDraft] = None
    target_weight_g: Optional[float] = Field(None, gt=0, le=500)
    budget_inr: Optional[float] = Field(None, gt=0, le=10_000_000)
    gem: Optional[Gem] = None
    gem_ct: Optional[float] = Field(None, gt=0, le=5)
    ring_size: Optional[int] = Field(None, ge=1, le=30)
    ring_inner_d_mm: Optional[float] = Field(None, ge=12, le=25)
    bangle_inner_d_mm: Optional[float] = Field(None, ge=45, le=75)
    length_in: Optional[ChainLength] = None
    style: list[str] = []

    @model_validator(mode='after')
    def _consistent_ring_size(self):
        if self.ring_size is not None and self.ring_inner_d_mm is not None:
            if abs(sizes.ring_inner_d_mm(self.ring_size) - self.ring_inner_d_mm) > 0.05:
                raise ValueError('Ring size and inner diameter conflict; ask which is correct')
        return self

    @field_validator("style", mode="before")
    @classmethod
    def _known_styles(cls, v):
        return style_tags(v)


@dataclass
class BriefResult:
    status: str                       # "brief" | "needs_info" | "out_of_scope"
    lang: str = EN
    brief: Brief | None = None
    reply: str = ""                   # joined questions or the scope reply
    questions: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    suggestion: str | None = None     # out_of_scope: nearest supported piece


# A number that starts where a digit run starts: never inside "12345" or right after "1.", so
# each unit regex is tried once per number, not once per digit (security F6: 20 KB of digits
# took 20+ s with unanchored "(\d+...)\s*unit" patterns).
NUM = r"(?<![\d.eE+\-])(?<!\d\.)(\d+(?:\.\d+)?)"


def _num(s: str) -> float:
    return float(s.replace(",", "").rstrip(","))


# ---------------------------------------------------------------- deterministic path

def _regex_parse(text: str) -> dict:
    t = text.lower()
    d: dict = {"style": []}
    for piece, pat in PIECE_WORDS.items():
        if re.search(pat, t):
            d["piece_type"] = piece
            break
    for g, pat in GEM_WORDS.items():
        if re.search(pat, t):
            d["gem"] = g
            break
    kms = list(re.finditer(r"\b(24|22|18|14)\s*-?\s*(k|kt|karat|carat|ct)\b", t))
    gem_ct = next((m for m in re.finditer(NUM + r"\s*(?:ct|carats?|cts)\b", t)
                   if _num(m.group(1)) < 6), None)
    if gem_ct:
        d["gem_ct"] = _num(gem_ct.group(1))
        d.setdefault("gem", "diamond")
    grams = re.search(NUM + r"\s*(?:g|gm|gms|gram|grams)\b", t)
    is_old = bool(re.search(OLD_WORDS, t))
    if grams and is_old:
        # The karat mentioned nearest the old-gold weight describes the old gold, unless it is
        # the only karat and it sits right before the new piece ("18K ring from my old 10 g").
        near = min(kms, key=lambda m: abs(m.start() - grams.start()), default=None)
        if (near and len(kms) == 1 and abs(near.start() - grams.start()) > 12
                and re.search(_ANY_PIECE, t[near.end():near.end() + 30])):
            near = None
        d["old_gold"] = {"weight_g": _num(grams.group(1))}
        if near:
            d["old_gold"]["karat"] = int(near.group(1))
        news = [int(m.group(1)) for m in kms if m is not near and m.group(1) != "24"]
        if news:
            d["karat"] = news[0]   # never copied from the old gold's karat
    else:
        if grams:
            d["target_weight_g"] = _num(grams.group(1))
        news = [int(m.group(1)) for m in kms if m.group(1) != "24"]
        if news:
            d["karat"] = news[0]
    lighter = re.search(_LIGHTER, t)
    pct = re.search(NUM + r"\s*%", t)
    if lighter and "target_weight_g" in d:
        # "it weighs 10 g, make it 20% lighter": the grams are the current weight.
        cur = d.pop("target_weight_g")
        if pct and 0 < _num(pct.group(1)) < 90:
            d["target_weight_g"] = round(cur * (1 - _num(pct.group(1)) / 100), 2)
    lakh = re.search(NUM + r"\s*(?:lakh|lac)", t)
    kbud = re.search(r"(?:₹|rs\.?|inr|budget|under|within)\s*(\d[\d,]*(?:\.\d+)?)(?![\d.,])\s*(k)?\b"
                     r"(?!\s*(?:g|gm|gms|grams?|ct|cts|carat|mm|days?|weeks?|months?|years?|hours?|minutes?)\b)", t)
    if lakh:
        d["budget_inr"] = _num(lakh.group(1)) * 100000
    elif kbud:
        d["budget_inr"] = _num(kbud.group(1)) * (1000 if kbud.group(2) else 1)
    for m in ("rose", "white", "yellow"):
        if re.search(rf"\b{m}\b", t):
            d["metal"] = m
    if d.get("piece_type") == "bangle":
        bsize = re.search(r"\b2\s*[-./]\s*(\d{1,2})\b(?!\s*(?:g|gm|gms|grams?|ct|mm|k)\b)", t)
        bmm = re.search(NUM + r"\s*mm\b", t)
        if bsize and int(bsize.group(1)) <= 15:
            d["bangle_inner_d_mm"] = sizes.bangle_inner_d_mm(int(bsize.group(1)))
        elif bmm:
            d["bangle_inner_d_mm"] = _num(bmm.group(1))
    if d.get("piece_type") == "chain":
        ln = re.search(CHAIN_LENGTH, t)
        if ln:
            d["length_in"] = int(ln.group(1))
    if d.get("piece_type") == "ring":
        us = re.search(r"\b(?:us\s*(?:size\s*)?|size\s*us\s*)(\d+(?:\.\d+)?)\b", t)
        rmm = re.search(NUM + r"\s*mm\b", t)
        rsize = re.search(r"\bsize\s*(?:no\.?\s*|number\s*)?(\d+(?:\.\d+)?)", t)
        if us:
            d["ring_inner_d_mm"] = sizes.us_ring_inner_d_mm(_num(us.group(1)))
        elif rmm:
            d["ring_inner_d_mm"] = _num(rmm.group(1))
        elif rsize:
            v = _num(rsize.group(1))
            if v.is_integer() and 1 <= v <= 30:
                d["ring_size"] = int(v)          # Indian size: this is an Indian shop
            # A fractional Indian size needs clarification; diameter requires explicit mm.
        if rsize and not us and not rmm and not _num(rsize.group(1)).is_integer():
            d.pop("ring_size", None)
        if rsize and rmm and not us:
            v = _num(rsize.group(1))
            if v.is_integer() and 1 <= v <= 30 and abs(sizes.ring_inner_d_mm(int(v)) - d["ring_inner_d_mm"]) > 0.05:
                d.pop("ring_inner_d_mm", None)
                d.pop("ring_size", None)
    for w, tag in STYLE_WORDS.items():
        if re.search(rf"\b{w}\b", t) and tag not in d["style"]:
            d["style"].append(tag)
    return d


def _regex_draft(text: str) -> tuple[BriefDraft, list[str]]:
    """Validated regex draft plus the fields that were stated but unreadable (dropped)."""
    d = _regex_parse(text)
    bad: list[str] = []
    while True:
        try:
            return BriefDraft(**d), bad
        except ValidationError as e:
            f = str(e.errors()[0]["loc"][0])
            bad.append(f)
            d.pop(f, None)


# ---------------------------------------------------------------- LLM path

def _validate(raw) -> BriefDraft:
    if not isinstance(raw, dict):
        raise TypeError(f"expected one JSON object, got {type(raw).__name__}")
    return BriefDraft.model_validate(raw)


def _llm_draft(text: str) -> BriefDraft | None:
    """LLM draft, repaired once with the validation error; None -> use the regex path."""
    raw = llm.complete_json(SYSTEM, text)
    if raw is None:
        return None
    try:
        return _validate(raw)
    except (ValidationError, TypeError) as e:
        err = str(e)
    fix = (f"{text}\n\nYour previous JSON was:\n{json.dumps(raw, ensure_ascii=False)[:2000]}\n"
           f"It failed validation:\n{err[:1500]}\nFix this JSON and return the corrected object only.")
    raw = llm.complete_json(SYSTEM, fix)
    if raw is None:
        return None
    try:
        return _validate(raw)
    except (ValidationError, TypeError):
        return None


# ---------------------------------------------------------------- decisions

def _out_of_scope(t: str) -> tuple[str, str, str] | None:
    """(English label, matched word, nearest piece) when only an unsupported piece is asked for."""
    if re.search(_ANY_PIECE, t):
        return None
    is_old = bool(re.search(OLD_WORDS, t))
    for pat, label, nearest, source in OUT_OF_SCOPE:
        m = re.search(pat, t)
        if m and not (source and is_old):
            return label, m.group(0), nearest
    return None


def _questions(d: BriefDraft, t: str, unreadable: list[str]) -> list[str]:
    topics: list[str] = []
    if not d.piece_type:
        topics.append("piece")
    if not (d.old_gold or d.target_weight_g or d.budget_inr):
        # "make this lighter" without a weight: ask for the reference piece (photo-to-spec is P1).
        topics.append("reference" if re.search(_LIGHTER, t) else "target")
    if "reference" not in topics:  # the reference question already asks for the size
        if d.piece_type == "ring" and d.ring_inner_d_mm is None and d.ring_size is None:
            topics.append("ring_size")
        if d.piece_type == "bangle" and d.bangle_inner_d_mm is None:
            topics.append("bangle_size")
        if d.piece_type == "chain" and d.length_in is None:
            topics.append("chain_length")
    if d.karat is None:
        topics.append("karat")
    if d.old_gold and d.old_gold.karat is None:
        topics.append("old_karat")
    for f in unreadable:
        if f not in ("ring_size", "ring_inner_d_mm", "bangle_inner_d_mm", "length_in", "karat",
                     "old_gold"):
            topics.append(f"unreadable:{f}")
    return topics[:MAX_QUESTIONS]


def _question_text(topic: str, lang: str) -> str:
    if topic.startswith("unreadable:"):
        return M.t("q_unreadable", lang, field=topic.split(":", 1)[1].replace("_", " "))
    return M.t(f"q_{topic}", lang)


def _defaults(d: BriefDraft, lang: str) -> list[str]:
    """Non-blocking fields left unstated: say which default is used."""
    notes = []
    if d.metal is None:
        notes.append(M.t("default_metal", lang))
    gem = d.gem or "none"
    if gem != "none" and not d.gem_ct:
        from .pricing import DEFAULT_CT
        ct = DEFAULT_CT.get(d.piece_type, 0)
        if ct:
            notes.append(M.t("default_stone", lang, ct=f"{ct:g}", piece=d.piece_type))
    return notes


def analyse(text: str, attachments=None) -> BriefResult:
    if len(text) > MAX_INPUT_CHARS:
        q = "Please shorten the request to 2,000 characters and include the piece, purity, size and weight or budget."
        return BriefResult("needs_info", EN, reply=q, questions=[q], topics=["request_length"])
    lang = detect(text)
    t = text.lower()
    oos = _out_of_scope(t)
    if oos:
        label, word, nearest = oos
        asked = label if lang == EN else word
        reply = M.t("out_of_scope", lang, asked=asked, nearest=nearest)
        return BriefResult("out_of_scope", lang, reply=reply, suggestion=nearest, topics=["scope"])

    draft = _llm_draft(text)
    unreadable: list[str] = []
    if draft is None:
        draft, unreadable = _regex_draft(text)

    topics = _questions(draft, t, unreadable)
    if topics:
        qs = [_question_text(x, lang) for x in topics]
        return BriefResult("needs_info", lang, reply=M.join_questions(qs, lang), questions=qs, topics=topics)

    fields = draft.model_dump(exclude_none=True)
    fam = family_from_text(draft.piece_type, t)    # family names come from code, never the LLM
    if fam:
        fields["family"] = fam
    fields["assumptions"] = _defaults(draft, lang)
    fields["lang"] = lang
    try:
        return BriefResult("brief", lang, brief=Brief(**fields))
    except (ValidationError, ValueError) as e:
        loc = e.errors()[0]["loc"] if isinstance(e, ValidationError) and e.errors()[0]["loc"] else ("request",)
        q = _question_text(f"unreadable:{loc[0]}", lang)
        return BriefResult("needs_info", lang, reply=q, questions=[q], topics=[f"unreadable:{loc[0]}"])


def parse(text: str) -> tuple[Brief | None, str | None]:
    """(Brief, None) or (None, reply). Kept for callers that only need the brief."""
    r = analyse(text)
    return (r.brief, None) if r.status == "brief" else (None, r.reply)


def describe(b: Brief, lang: str | None = None) -> str:
    lang = lang or b.lang
    if b.old_gold:
        src = M.t("src_old", lang, w=f"{b.old_gold.weight_g:g}", k=b.old_gold.karat)
    elif b.target_weight_g:
        src = M.t("src_weight", lang, w=f"{b.target_weight_g:g}")
    else:
        src = M.t("src_budget", lang, b=inr(b.budget_inr))
    gem = f", {b.gem}{f' {b.gem_ct:g} ct' if b.gem_ct else ''}" if b.gem != "none" else ""
    style = f", style: {', '.join(b.style)}" if b.style else ""
    s = M.t("summary", lang, article="An" if b.karat == 18 else "A", karat=b.karat, metal=b.metal,
            piece=b.piece_type, src=src, gem=gem, style=style)
    if b.assumptions:
        s += " " + " ".join(b.assumptions)
    return s
