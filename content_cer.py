#!/usr/bin/env python3
"""Calculate Strict CER and Content CER for Thai ASR transcripts.

Content CER converts valid Thai cardinal-number expressions to Arabic digits
with a grammar-based parser. It does not use a fixed map of full phrases.
The parser supports units, tens, hundreds, thousands, ten-thousands,
hundred-thousands, millions, Thai digits, and mixed Arabic-digit expressions
such as ``5ล้าน4แสน``.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


THAI_DIGIT_TRANSLATION = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
THAI_NUMBER_WORDS = {
    "ศูนย์": 0,
    "หนึ่ง": 1,
    "เอ็ด": 1,
    "สอง": 2,
    "ยี่": 2,
    "สาม": 3,
    "สี่": 4,
    "ห้า": 5,
    "หก": 6,
    "เจ็ด": 7,
    "แปด": 8,
    "เก้า": 9,
}
THAI_NUMBER_MULTIPLIERS = {
    "สิบ": 10,
    "ร้อย": 100,
    "พัน": 1_000,
    "หมื่น": 10_000,
    "แสน": 100_000,
    "ล้าน": 1_000_000,
}
NUMBER_TOKENS = sorted(
    [*THAI_NUMBER_WORDS, *THAI_NUMBER_MULTIPLIERS], key=len, reverse=True
)
TOKEN_ALTERNATION = "|".join(map(re.escape, NUMBER_TOKENS))
NUMBER_TOKEN_PATTERN = re.compile(rf"\d+|[๐-๙]+|{TOKEN_ALTERNATION}")
NUMBER_CANDIDATE_PATTERN = re.compile(
    rf"(?:\d+|[๐-๙]+|{TOKEN_ALTERNATION})+"
)

# Isolated unit words are ambiguous: for example, ศูนย์ต่อต้าน means
# "anti-fraud center", not numeric zero. Convert a one-word unit only where
# the adjacent text strongly suggests a count or date.
STANDALONE_NUMBER_PREFIXES = ("วันที่", "อายุ", "จำนวน", "รวม", "มี", "ได้")
STANDALONE_NUMBER_SUFFIXES = (
    "บาท",
    "ปี",
    "คดี",
    "เครื่อง",
    "คน",
    "ราย",
    "ครั้ง",
    "ตัว",
    "ถึง",
    "โมง",
    "วัน",
    "เดือน",
    "อันดับ",
    "เปอร์เซ็นต์",
    "%",
)


def normalize_strict(text: str) -> str:
    """Apply the Unicode/whitespace normalization used by Strict CER."""
    normalized = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", "", normalized).replace("\u200b", "")


def remove_suffixes(text: str, suffixes: list[str]) -> str:
    """Remove only suffixes explicitly declared by the caller."""
    for suffix in suffixes:
        normalized_suffix = normalize_strict(suffix)
        if normalized_suffix and text.endswith(normalized_suffix):
            text = text[: -len(normalized_suffix)]
    return text


def tokenize_number_phrase(phrase: str) -> list[str] | None:
    """Return full tokens for a candidate phrase, or None if it is partial."""
    tokens = NUMBER_TOKEN_PATTERN.findall(phrase)
    return tokens if tokens and "".join(tokens) == phrase else None


def token_to_integer(token: str) -> int | None:
    """Translate an Arabic/Thai digit token; return None for a Thai word."""
    if token.isdecimal():
        return int(token.translate(THAI_DIGIT_TRANSLATION))
    return None


def parse_thai_number_phrase(phrase: str) -> int | None:
    """Parse one complete Thai cardinal-number expression.

    Examples: ``สิบเอ็ด`` -> 11, ``ห้าล้านสี่แสน`` -> 5400000,
    and ``5ล้าน4แสน`` -> 5400000. Invalid multiplier ordering returns None.
    """
    tokens = tokenize_number_phrase(phrase)
    if tokens is None:
        return None

    total = 0
    section = 0
    current: int | None = None
    last_multiplier = float("inf")

    for token in tokens:
        numeric = token_to_integer(token)
        if numeric is not None:
            if current is not None:
                return None
            current = numeric
            continue

        if token in THAI_NUMBER_WORDS:
            if current is not None:
                return None
            current = THAI_NUMBER_WORDS[token]
            continue

        multiplier = THAI_NUMBER_MULTIPLIERS[token]
        if multiplier == 1_000_000:
            section += 0 if current is None else current
            if section == 0:
                return None
            total = (total + section) * multiplier
            section = 0
            current = None
            last_multiplier = float("inf")
            continue

        if multiplier >= last_multiplier:
            return None
        section += (1 if current is None else current) * multiplier
        current = None
        last_multiplier = multiplier

    return total + section + (0 if current is None else current)


def should_convert_candidate(text: str, start: int, end: int, tokens: list[str]) -> bool:
    """Reject ambiguous isolated Thai unit words unless their context is numeric."""
    if any(token in THAI_NUMBER_MULTIPLIERS or token.isdecimal() for token in tokens):
        return True
    if len(tokens) != 1 or tokens[0] not in THAI_NUMBER_WORDS:
        return False

    before = text[max(0, start - 12) : start]
    after = text[end : end + 16]
    return before.endswith(STANDALONE_NUMBER_PREFIXES) or after.startswith(
        STANDALONE_NUMBER_SUFFIXES
    )


def thai_number_words_to_arabic(text: str) -> str:
    """Convert unambiguous Thai cardinal-number phrases in free text to digits.

    The function keeps ambiguous standalone words intact. This avoids changing
    non-numeric uses such as ``ศูนย์ต่อต้าน`` while still converting forms such
    as ``สองเครื่อง``, ``วันที่ห้า``, and ``สามร้อยเก้าสิบเจ็ด``.
    """

    def replace(match: re.Match[str]) -> str:
        phrase = match.group(0)
        tokens = tokenize_number_phrase(phrase)
        value = parse_thai_number_phrase(phrase)
        if tokens is None or value is None:
            return phrase
        if not should_convert_candidate(text, match.start(), match.end(), tokens):
            return phrase
        return str(value)

    return NUMBER_CANDIDATE_PATTERN.sub(replace, text)


def normalize_content(text: str, suffixes: list[str]) -> str:
    """Apply Content CER rules to one transcript."""
    normalized = remove_suffixes(normalize_strict(text), suffixes)
    normalized = normalized.replace("ํา", "ำ").replace(",", "")
    return thai_number_words_to_arabic(normalized)


def edit_distance(reference: str, hypothesis: str) -> int:
    """Return character-level Levenshtein distance using O(min(m, n)) memory."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for reference_character in reference:
        current = [previous[0] + 1]
        for index, hypothesis_character in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index] + 1,
                    previous[index - 1]
                    + (reference_character != hypothesis_character),
                )
            )
        previous = current
    return previous[-1]


def score(reference: str, hypothesis: str) -> dict[str, int | float]:
    if not reference:
        raise ValueError("The normalized reference is empty; CER is undefined.")
    errors = edit_distance(reference, hypothesis)
    return {
        "reference_characters": len(reference),
        "character_errors": errors,
        "cer": errors / len(reference),
        "cer_percent": round(errors / len(reference) * 100, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate Thai ASR Strict CER and grammar-based Content CER."
    )
    parser.add_argument("--reference-file", type=Path, required=True)
    parser.add_argument("--hypothesis-file", type=Path, required=True)
    parser.add_argument(
        "--reference-suffix",
        action="append",
        default=[],
        help="Suffix to exclude from the reference only; repeat as needed.",
    )
    parser.add_argument(
        "--hypothesis-suffix",
        action="append",
        default=[],
        help="Suffix to exclude from the hypothesis only; repeat as needed.",
    )
    parser.add_argument(
        "--show-normalized",
        action="store_true",
        help="Include normalized text in JSON. Avoid this for sensitive transcripts.",
    )
    args = parser.parse_args()

    raw_reference = args.reference_file.read_text(encoding="utf-8")
    raw_hypothesis = args.hypothesis_file.read_text(encoding="utf-8")
    strict_reference = normalize_strict(raw_reference)
    strict_hypothesis = normalize_strict(raw_hypothesis)
    content_reference = normalize_content(raw_reference, args.reference_suffix)
    content_hypothesis = normalize_content(raw_hypothesis, args.hypothesis_suffix)

    result: dict[str, object] = {
        "strict_cer": score(strict_reference, strict_hypothesis),
        "content_cer": score(content_reference, content_hypothesis),
        "content_rules": {
            "thai_number_parser": "grammar-based Thai cardinal numbers to Arabic digits",
            "supported_scales": ["สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน"],
            "supports_thai_digits": True,
            "supports_mixed_arabic_digit_forms": True,
            "ambiguous_standalone_units": "converted only in count/date context",
            "remove_thousands_separators": True,
            "equate_thai_forms": ["ํา", "ำ"],
            "reference_suffixes_removed": args.reference_suffix,
            "hypothesis_suffixes_removed": args.hypothesis_suffix,
        },
    }
    if args.show_normalized:
        result["normalized"] = {
            "strict_reference": strict_reference,
            "strict_hypothesis": strict_hypothesis,
            "content_reference": content_reference,
            "content_hypothesis": content_hypothesis,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
