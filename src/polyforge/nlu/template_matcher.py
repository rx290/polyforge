"""Zero-dependency, zero-ML text-to-template matcher.

Picks one template from the bounded library (polyforge.templates) by keyword
match (with a fuzzy fallback for typos), then fills its parameters by pattern-
matching common phrasings: WxDxH dimension triples, screw sizes ("M3"), and
hole/slot counts ("4 holes", "four slots"). This never invents geometry outside
the known template vocabulary; for open-ended descriptions, use the
`llm_backend` engine instead (`polyforge design --engine llm ...`).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .. import templates

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "twenty": 20,
}

# Screw nominal diameter (mm) -> standard clearance hole diameter (mm).
SCREW_CLEARANCE_MM = {2.0: 2.4, 2.5: 2.9, 3.0: 3.4, 4.0: 4.5, 5.0: 5.5, 6.0: 6.6, 8.0: 9.0}

# Which param on each template a screw size ("M3") should set, if any.
DIAMETER_PARAM = {
    "shelf_bracket": "hole_diameter",
    "l_bracket": "hole_diameter",
    "standoff_mount": "hole_diameter",
}

# Which param on each template a "N holes/slots" count should set, if any.
COUNT_PARAM = {
    "shelf_bracket": "hole_count",
    "l_bracket": "holes_per_flange",
    "cable_comb": "slot_count",
}

_UNIT = r"(mm|cm|in|inch(?:es)?)?"
_NUM = r"(\d+(?:\.\d+)?)"
_DIM_TRIPLE_RE = re.compile(
    rf"{_NUM}\s*{_UNIT}\s*(?:x|by|×)\s*{_NUM}\s*{_UNIT}\s*(?:x|by|×)\s*{_NUM}\s*{_UNIT}",
    re.IGNORECASE,
)
_DIM_PAIR_RE = re.compile(rf"{_NUM}\s*{_UNIT}\s*(?:x|by|×)\s*{_NUM}\s*{_UNIT}", re.IGNORECASE)
_SCREW_RE = re.compile(r"\bm(2\.5|2|3|4|5|6|8)\b", re.IGNORECASE)
_COUNT_RE = re.compile(
    r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(?:m\d+(?:\.\d+)?\s+)?(holes?|slots?|standoffs?)\b",
    re.IGNORECASE,
)


class NoTemplateMatchError(Exception):
    """Raised when no known template plausibly matches the request text."""


@dataclass
class MatchResult:
    template_key: str
    confidence: float
    params: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def _to_mm(value: float, unit: str | None) -> float:
    unit = (unit or "mm").lower()
    if unit == "cm":
        return value * 10
    if unit.startswith("in"):
        return value * 25.4
    return value


def _score_template(text_l: str, template) -> tuple[int, list[str]]:
    matched = [kw for kw in template.keywords if kw in text_l]
    score = sum(len(kw.split()) for kw in matched)
    return score, matched


def _fuzzy_pick(text_l: str):
    words = re.findall(r"[a-z]+", text_l)
    best = None  # (ratio, template, matched_keyword, input_word)
    for template in templates.all_templates():
        keyword_words = {w for kw in template.keywords for w in kw.split()}
        for word in words:
            close = difflib.get_close_matches(word, keyword_words, n=1, cutoff=0.75)
            if not close:
                continue
            ratio = difflib.SequenceMatcher(None, word, close[0]).ratio()
            if best is None or ratio > best[0]:
                best = (ratio, template, close[0], word)
    return best


def pick_template(text: str):
    text_l = text.lower()
    scored = [(*_score_template(text_l, t), t) for t in templates.all_templates()]
    scored = [s for s in scored if s[0] > 0]
    if scored:
        scored.sort(key=lambda s: s[0], reverse=True)
        top_score, top_matched, top_template = scored[0]
        confidence = min(1.0, 0.55 + 0.15 * len(top_matched))
        return top_template, confidence, [f"matched keywords: {top_matched}"]

    fuzzy = _fuzzy_pick(text_l)
    if fuzzy:
        ratio, template, keyword, word = fuzzy
        confidence = round(0.35 + 0.3 * ratio, 2)
        return template, confidence, [f"fuzzy match: {word!r} ~ {keyword!r} ({ratio:.2f})"]

    known = ", ".join(sorted(t.key for t in templates.all_templates()))
    raise NoTemplateMatchError(f"Could not match a known part template in: {text!r}. Known templates: {known}")


def _effective_unit(raw_units: list) -> str:
    # A shorthand like "6x4x3cm" only trails the unit once; that one unit
    # governs every number in the group rather than just the last one.
    return next((u for u in raw_units if u), "mm")


def extract_params(text: str, template) -> tuple[dict, list[str]]:
    text_l = text.lower()
    params: dict = {}
    notes: list[str] = []
    dim_names = [p.name for p in template.params[:3]]

    triple = _DIM_TRIPLE_RE.search(text_l)
    if triple:
        raw = [(float(triple.group(1)), triple.group(2)), (float(triple.group(3)), triple.group(4)), (float(triple.group(5)), triple.group(6))]
        unit = _effective_unit([u for _, u in raw])
        values = [_to_mm(v, unit) for v, _ in raw]
        params.update(zip(dim_names, (round(v, 3) for v in values)))
        notes.append(f"dimensions {values} mm -> {dim_names}")
    else:
        pair = _DIM_PAIR_RE.search(text_l)
        if pair:
            raw = [(float(pair.group(1)), pair.group(2)), (float(pair.group(3)), pair.group(4))]
            unit = _effective_unit([u for _, u in raw])
            values = [_to_mm(v, unit) for v, _ in raw]
            params.update(zip(dim_names, (round(v, 3) for v in values)))
            notes.append(f"dimensions {values} mm -> {dim_names[:2]}")

    diameter_param = DIAMETER_PARAM.get(template.key)
    screw = _SCREW_RE.search(text_l)
    if screw and diameter_param:
        size = float(screw.group(1))
        clearance = SCREW_CLEARANCE_MM.get(size)
        if clearance:
            params[diameter_param] = clearance
            notes.append(f"M{screw.group(1)} screw -> {diameter_param} = {clearance} mm clearance")

    count_param = COUNT_PARAM.get(template.key)
    count = _COUNT_RE.search(text_l)
    if count and count_param:
        raw = count.group(1)
        n = NUMBER_WORDS.get(raw, None)
        n = int(raw) if n is None else n
        params[count_param] = n
        notes.append(f"count {n!r} -> {count_param}")

    return params, notes


def match(text: str) -> MatchResult:
    if not text or not text.strip():
        raise NoTemplateMatchError("empty request text")
    template, confidence, pick_notes = pick_template(text)
    params, extract_notes = extract_params(text, template)
    return MatchResult(template_key=template.key, confidence=confidence, params=params, notes=pick_notes + extract_notes)
