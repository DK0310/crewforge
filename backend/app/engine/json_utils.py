"""Tolerant JSON extraction + schema validation for worker output.

Local models occasionally wrap JSON in code fences or add a stray preamble. We
extract the JSON object, then validate it against the agent's `output_schema`.
The worker node uses these to implement validate-and-repair-once.
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema


class JsonValidationError(ValueError):
    """Raised when output can't be parsed or fails its schema."""


def extract_json(raw: str) -> Any:
    """Parse JSON from a model response, tolerating code fences / preamble."""
    text = raw.strip()
    # Fast path.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip a ```json ... ``` fence if present.
    if "```" in text:
        fenced = text.split("```")
        for block in fenced:
            block = block.removeprefix("json").strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

    # Last resort: grab the outermost {...} or [...] span.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = text.find(open_ch), text.rfind(close_ch)
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise JsonValidationError("no JSON object found in model output")


def validate_output(raw: str, schema: dict) -> dict:
    """Extract JSON from `raw` and validate it against `schema`. Raises
    `JsonValidationError` on any failure.
    """
    data = extract_json(raw)
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise JsonValidationError(f"output does not match schema: {exc.message}") from exc
    if not isinstance(data, dict):
        raise JsonValidationError("worker output must be a JSON object")
    return data
