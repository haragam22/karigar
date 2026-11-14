"""Jewellery specs. The LLM designer may only produce these; the builder turns
them into geometry deterministically, so every design is a valid solid."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import sizes

PieceType = Literal["ring", "bangle", "pendant", "chain", "coin", "earring", "nosepin"]
ChainLength = Literal[16, 18, 20, 22, 24]          # inches, the lengths Indian shops stock
Gem = Literal["none", "diamond", "ruby", "emerald", "sapphire"]
Metal = Literal["yellow", "rose", "white"]
Karat = Literal[22, 18, 14]

# Specific gravity relative to diamond, for carat <-> diameter estimates.
GEM_SG = {"diamond": 3.52, "ruby": 4.0, "sapphire": 4.0, "emerald": 2.72}


# Style vocabulary: customer word -> tag. A Brief keeps only these tags, so free text (an LLM
# string, a price, a payment instruction) can never reach a reply through `style` (security F8).
STYLE_WORDS = {
    # concrete motifs the designer can match
    "lotus": "lotus", "kamal": "lotus", "beaded": "beaded", "plain": "plain", "knife": "knife",
    "faceted": "faceted", "coin": "coin", "flat": "flat", "floral": "floral", "flower": "floral",
    "flowers": "floral", "phool": "floral",
    # ambiguous words: recorded, never asked about; the designer spreads 3 variants
    "minimal": "minimal", "traditional": "traditional", "modern": "modern", "simple": "simple",
    "classic": "classic", "contemporary": "modern", "ethnic": "traditional", "heavy": "heavy look",
    "bold": "bold", "delicate": "delicate", "sleek": "modern",
}
STYLE_TAGS = frozenset(STYLE_WORDS.values())


def style_tags(items) -> list[str]:
    """Known style tags from a list of words, in order, deduplicated; anything else is dropped."""
    if not isinstance(items, (list, tuple)):
        return items                       # let the field type reject it
    out: list[str] = []
    for w in items:
        if not isinstance(w, str):
            continue
        w = w.strip().lower()
        tag = STYLE_WORDS.get(w) or (w if w in STYLE_TAGS else None)
        if tag and tag not in out:
            out.append(tag)
    return out


def _known_family(v):
    """A family must be in the Phase 2.5 catalogue or registered (tests add throwaway ones)."""
    if v in (None, ""):
        return v
    from .families import CATALOGUE, FAMILIES
    if v not in CATALOGUE and v not in FAMILIES:
        raise ValueError(f"unknown design family {v!r}")
    return v


def gem_ct_from_d(gem: str, d_mm: float) -> float:
    """Round brilliant approximation: 6.5 mm diamond ~ 1.0 ct."""
    if gem == "none" or d_mm <= 0:
        return 0.0
    return 0.0037 * d_mm ** 3 * GEM_SG[gem] / GEM_SG["diamond"]


def gem_d_from_ct(gem: str, ct: float) -> float:
    return (ct / (0.0037 * GEM_SG[gem] / GEM_SG["diamond"])) ** (1 / 3)


class OldGold(BaseModel):
    """Credited at its karat's purity only; any claimed/tested purity is ignored (security F9)."""
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    weight_g: float = Field(gt=0, le=500)
    karat: Literal[24, 22, 18, 14] = 22


class Brief(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)   # inf/NaN never reach pricing (security F7)
    piece_type: PieceType
    karat: Karat = 22
    metal: Metal = "yellow"
    old_gold: Optional[OldGold] = None
    target_weight_g: Optional[float] = Field(None, gt=0, le=500)   # finished weight
    budget_inr: Optional[float] = Field(None, gt=0, le=10_000_000)
    gem: Gem = "none"
    gem_ct: Optional[float] = Field(None, gt=0, le=5)
    # Canonical ring size is the inner diameter. `ring_size` (Indian, 1-30) converts through
    # data/ring_sizes.json. The schema defaults below are for code paths that build a Brief
    # directly; brief.parse never relies on them (it asks for the size instead).
    ring_size: Optional[int] = Field(None, ge=1, le=30)
    ring_inner_d_mm: float = Field(17.3, ge=12, le=25)
    bangle_inner_d_mm: float = Field(60.3, ge=45, le=75)    # Indian size 2-6
    length_in: Optional[ChainLength] = None                 # chain length; brief asks if missing
    family: Optional[str] = None                            # a catalogue family named by the customer
    style: list[str] = []
    assumptions: list[str] = []
    lang: Literal["en", "hinglish"] = "en"                  # reply language of the request

    @field_validator("style", mode="before")
    @classmethod
    def _known_styles(cls, v):
        return style_tags(v)

    @field_validator("family")
    @classmethod
    def _family(cls, v):
        return _known_family(v)

    @model_validator(mode="before")
    @classmethod
    def _ring_size_to_mm(cls, data):
        if (isinstance(data, dict) and data.get("ring_size") is not None
                and data.get("ring_inner_d_mm") is None):
            size = data["ring_size"]
            if isinstance(size, str):
                try:
                    size = float(size)
                except ValueError:
                    pass
            if isinstance(size, (int, float)) and 1 <= size <= 30 and float(size).is_integer():
                data = {**data, "ring_inner_d_mm": sizes.ring_inner_d_mm(int(size))}
        return data


# Which motifs each piece is built with (the pendant's look comes from `shape`).
MOTIFS = {"ring": ("plain", "floral"), "bangle": ("plain", "beaded"), "pendant": ("plain",),
          "chain": ("plain",), "coin": ("plain",), "earring": ("plain",), "nosepin": ("plain",)}
PARAM_KEY = r"^[a-z][a-z0-9_]{0,31}$"
MAX_PARAMS = 24


class DesignSpec(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    name: str
    piece_type: PieceType
    karat: Karat = 22
    metal: Metal = "yellow"
    # band (ring / bangle). Width/thickness are at scale 1.0; the solver scales them.
    profile: Literal["comfort", "flat", "knife", "faceted"] = "comfort"
    inner_d_mm: float = Field(17.3, ge=12, le=75)
    width_mm: float = Field(3.0, ge=1.0, le=16)
    thickness_mm: float = Field(1.8, ge=0.6, le=6)
    # stone + setting
    gem: Gem = "none"
    gem_d_mm: float = Field(0.0, ge=0, le=12)
    prongs: Literal[4, 6] = 4
    # motif: "beaded" = bangle beads; "floral" = ring with a flower top (petals, size_mm)
    motif: Literal["plain", "beaded", "floral"] = "plain"
    bead_count: int = Field(24, ge=8, le=72)
    # pendant (size_mm/petals also give a floral ring's flower diameter and petal count)
    shape: Literal["disc", "lotus"] = "lotus"
    size_mm: float = Field(18.0, ge=8, le=45)
    petals: int = Field(8, ge=5, le=12)
    # Phase 2.5 catalogue. family "" = the original ring/bangle/pendant builders.
    family: str = ""
    length_in: Optional[ChainLength] = None    # chain length (inches); required for a chain
    link_w_mm: float = Field(3.0, ge=0.8, le=12)   # chain link / wire width
    pair: bool = True                          # earrings are made and weighed as a pair
    gauge_mm: float = Field(0.8, ge=0.6, le=1.5)   # nose-pin / ear-post wire gauge
    stamp: bool = True                         # coin: emboss karat + weight on the back
    params: dict[str, float] = {}              # family-own numeric knobs (families/__init__.py)
    rationale: str = ""

    @field_validator("family")
    @classmethod
    def _family(cls, v):
        return _known_family(v)

    @field_validator("params")
    @classmethod
    def _params(cls, v):
        import math
        import re
        if len(v) > MAX_PARAMS:
            raise ValueError(f"at most {MAX_PARAMS} family params")
        for k, x in v.items():
            if not re.match(PARAM_KEY, k):
                raise ValueError(f"param name {k!r} must match {PARAM_KEY}")
            if not math.isfinite(x) or not -1000 <= x <= 1000:
                raise ValueError(f"param {k!r} must be a finite number in [-1000, 1000]")
        return v

    @model_validator(mode="after")
    def _chain_has_length(self):
        if self.piece_type == "chain" and self.length_in is None:
            raise ValueError("a chain needs length_in (16, 18, 20, 22 or 24 inches)")
        return self

    @model_validator(mode="after")
    def _motif_fits_piece(self):
        allowed = MOTIFS[self.piece_type]
        if self.motif not in allowed:
            raise ValueError(f"motif '{self.motif}' is not made for a {self.piece_type}; "
                             f"use one of {', '.join(allowed)}")
        return self

    @property
    def gem_ct(self) -> float:
        return gem_ct_from_d(self.gem, self.gem_d_mm)
