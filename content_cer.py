#!/usr/bin/env python3
"""Compare Strict CER and Content CER for Thai ASR transcripts.

Strict CER only normalizes Unicode and whitespace. Content CER additionally
applies declared, auditable representation rules before scoring. The bundled
number map covers the spoken-number forms in this repository's test clip; add
or replace mappings for another domain instead of treating it as a universal
Thai text normalizer.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Mapping


# Clip-specific examples. Longer forms must be substituted before their parts.
DEFAULT_THAI_NUMBER_MAP: dict[str, str] = {
    "หนึ่งแสนห้าหมื่น": "150000",
    "ห้าล้านสี่แสน": "5400000",
    "สองร้อยสิบสาม": "213",
    "สามร้อยเก้าสิบเจ็ด": "397",
    "เจ็ดพันสามร้อย": "7300",
    "หนึ่งแสน": "100000",
    "ห้าพัน": "5000",
    "สิบเก้า": "19",
    "สิบเจ็ด": "17",
    "สิบเอ็ด": "11",
    "5ล้าน4แสน": "5400000",
    "ห้า": "5",
    "สอง": "2",
}


def normalize_strict(text: str) -> str:
    """Apply the normalization used by Strict CER in this benchmark."""
    normalized = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", "", normalized).replace("\u200b", "")


def remove_suffixes(text: str, suffixes: list[str]) -> str:
    """Remove only explicitly declared suffixes after strict normalization."""
    for suffix in suffixes:
        normalized_suffix = normalize_strict(suffix)
        if normalized_suffix and text.endswith(normalized_suffix):
            text = text[: -len(normalized_suffix)]
    return text


def normalize_content(
    text: str,
    number_map: Mapping[str, str],
    suffixes: list[str],
) -> str:
    """Apply auditable Content CER rules to one side of the comparison."""
    normalized = remove_suffixes(normalize_strict(text), suffixes)
    normalized = normalized.replace("ํา", "ำ").replace(",", "")
    for thai_form in sorted(number_map, key=len, reverse=True):
        normalized = normalized.replace(thai_form, str(number_map[thai_form]))
    return normalized


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


def score(reference: str, hypothesis: str) -> dict[str, int | float | str]:
    if not reference:
        raise ValueError("The normalized reference is empty; CER is undefined.")
    errors = edit_distance(reference, hypothesis)
    return {
        "reference_characters": len(reference),
        "character_errors": errors,
        "cer": errors / len(reference),
        "cer_percent": round(errors / len(reference) * 100, 4),
    }


def load_number_map(path: Path | None, use_default_map: bool) -> dict[str, str]:
    number_map = dict(DEFAULT_THAI_NUMBER_MAP) if use_default_map else {}
    if path is None:
        return number_map
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not all(
        isinstance(key, str) and isinstance(value, (str, int))
        for key, value in loaded.items()
    ):
        raise ValueError("--number-map-json must be an object of string keys and string/integer values.")
    number_map.update({key: str(value) for key, value in loaded.items()})
    return number_map


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate Thai ASR Strict CER and Content CER from two UTF-8 text files."
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
        "--number-map-json",
        type=Path,
        help="Optional JSON object of additional/replacement Thai-number mappings.",
    )
    parser.add_argument(
        "--no-default-number-map",
        action="store_true",
        help="Start with an empty map; use only --number-map-json mappings.",
    )
    parser.add_argument(
        "--show-normalized",
        action="store_true",
        help="Include the normalized strings in the JSON result. Avoid this for sensitive transcripts.",
    )
    args = parser.parse_args()

    raw_reference = args.reference_file.read_text(encoding="utf-8")
    raw_hypothesis = args.hypothesis_file.read_text(encoding="utf-8")
    number_map = load_number_map(args.number_map_json, not args.no_default_number_map)

    strict_reference = normalize_strict(raw_reference)
    strict_hypothesis = normalize_strict(raw_hypothesis)
    content_reference = normalize_content(
        raw_reference, number_map, args.reference_suffix
    )
    content_hypothesis = normalize_content(
        raw_hypothesis, number_map, args.hypothesis_suffix
    )

    result: dict[str, object] = {
        "strict_cer": score(strict_reference, strict_hypothesis),
        "content_cer": score(content_reference, content_hypothesis),
        "content_rules": {
            "number_map_entries": len(number_map),
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
