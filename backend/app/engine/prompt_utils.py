"""Small shared helpers for assembling node prompts."""

from __future__ import annotations


def source_material_block(uploaded: str | None, max_chars: int) -> str:
    """Format the user's uploaded file as a prompt block, capped to `max_chars`.

    Returns "" when there is no upload, so callers can drop it cleanly. The cap is
    the main defense against a large upload blowing the model's context window.
    """
    if not uploaded or not uploaded.strip():
        return ""
    text = uploaded.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n…[truncated; {len(uploaded)} chars total]"
    return "Source material (uploaded by the user):\n" + text
