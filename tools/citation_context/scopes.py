"""Small, source-offset quotation scopes shared by the context experiments.

The corpus uses one line per extracted paragraph. An unmatched delimiter is
therefore bounded by that paragraph, never carried into the rest of a judgment.
Mixed straight/curly double quotes are retained as uncertain evidence. Apostrophes
are deliberately excluded because they occur in party names and French prose.
"""
from __future__ import annotations

import re


_OPENERS = {"“": "”", "«": "»", '"': '"'}
_CLOSERS = frozenset(("”", "»"))


def _closing_context(text, position, paragraph_end):
    return (position > 0 and not text[position - 1].isspace()
            and (position + 1 == paragraph_end or not text[position + 1].isalnum()))


def quotation_scopes(text: str) -> list[dict]:
    """Return nested paragraph-bounded quote spans in original Unicode offsets.

    ``closed`` describes observed delimiter evidence; ``uncertain`` is also true
    for a mixed double-quote pair, an orphan closer or an unclosed ancestor.
    ``start/end`` include observed delimiters; ``content_start/content_end`` do
    not. IDs depend only on original source offsets, not caller traversal order.
    """
    scopes = []
    for paragraph in re.finditer(r"[^\r\n]+", text):
        stack = []
        for position in range(paragraph.start(), paragraph.end()):
            char = text[position]
            if stack and (char == stack[-1]["expected"]
                          or char in {'"', "”"} and stack[-1]["opener"] in {'"', "“"}
                          and _closing_context(text, position, paragraph.end())):
                scope = stack.pop()
                mixed = char != scope.pop("expected")
                scope.update(end=position + 1, content_end=position, closer=char,
                             closed=True, uncertain=mixed,
                             boundary_reason="mixed_double_quote_pair" if mixed else "balanced_delimiters")
                scopes.append(scope)
            elif char in _OPENERS:
                parent = stack[-1] if stack else None
                stack.append({"scope_id": "quote-" + str(position), "start": position,
                              "content_start": position + 1, "opener": char,
                              "expected": _OPENERS[char], "depth": len(stack),
                              "parent_scope_id": parent["scope_id"] if parent else None})
            elif char in _CLOSERS:
                # A closing glyph without its opener is evidence of damaged
                # quotation extraction, not proof of current-court narration.
                scopes.append({"scope_id": "quote-orphan-" + str(position),
                               "start": paragraph.start(), "end": position + 1,
                               "content_start": paragraph.start(), "content_end": position,
                               "opener": None, "closer": char, "depth": len(stack),
                               "parent_scope_id": stack[-1]["scope_id"] if stack else None,
                               "closed": False, "uncertain": True,
                               "boundary_reason": "orphan_closing_delimiter"})
        for scope in stack:
            scope.pop("expected")
            scope.update(end=paragraph.end(), content_end=paragraph.end(), closer=None,
                         closed=False, uncertain=True, boundary_reason="unclosed_at_paragraph_end")
            scopes.append(scope)
    scopes.sort(key=lambda scope: (scope["start"], -scope["end"], scope["depth"]))
    by_id = {scope["scope_id"]: scope for scope in scopes}
    for scope in scopes:
        parent = by_id.get(scope["parent_scope_id"])
        if parent and parent["uncertain"]:
            scope["uncertain"] = True
            scope["boundary_reason"] = "uncertain_ancestor"
    return scopes


def quote_scope_at(position: int, scopes: list[dict]) -> dict | None:
    """Return the innermost content scope containing ``position``, if any."""
    matches = [scope for scope in scopes
               if scope["content_start"] <= position < scope["content_end"]]
    return max(matches, key=lambda scope: (scope["depth"], scope["start"])) if matches else None


def quote_scope_for_span(start: int, end: int, scopes: list[dict]) -> dict | None:
    """Return a common innermost scope for a nonempty original-text span."""
    first = quote_scope_at(start, scopes)
    last = quote_scope_at(end - 1, scopes) if end > start else None
    return first if first and last and first["scope_id"] == last["scope_id"] else None


def quote_scope_evidence(scope: dict | None) -> dict | None:
    """Copy auditable scope metadata without exposing mutable parser objects."""
    return dict(scope) if scope is not None else None


def quotation_ranges(text: str) -> list[tuple[int, int]]:
    """Compatibility view for lexical quote-title checks."""
    return [(scope["start"], scope["end"]) for scope in quotation_scopes(text)]
