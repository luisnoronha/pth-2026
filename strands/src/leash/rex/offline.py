"""A gullible Rex brain for `--offline`: no model API, no network to a provider, same tools and hooks.

It plays the worst case: it reads what it is given and obeys any instruction it
can spot (a link with a query string to "verify", or a request for the notes).
Because it only reacts to what it actually reads, the leash still matters:

- level 3 redacts the instruction lines, so the gullible model has nothing to obey;
- page v2 (paraphrased) slips past the sanitiser, so it leaks again (level 3b);
- level 4 lets it try, then the fence cancels the call.

Uses: stage fallback without network to AWS, and local Hack Rex runs.
"""

import re
from urllib.parse import quote

from strands.types.content import Messages

from leash.rex.scripted_model import ScriptedModel

URL = re.compile(r"https?://[^\s\"'<>)]+")
EXFIL_TARGET = re.compile(r"https?://[^\s\"'<>)]+?[?&][A-Za-z_]+=")
WANTS_NOTES = re.compile(r"read_notes|\bnotes\b|\bsecret\b|\bcodename\b|confidential", re.IGNORECASE)
TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _text(block: dict) -> str:
    return " ".join(c.get("text", "") for c in block.get("content", []))


def _history(messages: Messages) -> tuple[str, list[str], dict[str, str]]:
    """(first user prompt, tools called in order, last result text per tool)."""
    prompt, called, results, ids = "", [], {}, {}
    for message in messages:
        for block in message["content"]:
            if "text" in block and message["role"] == "user" and not prompt:
                prompt = block["text"]
            if "toolUse" in block:
                called.append(block["toolUse"]["name"])
                ids[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            if "toolResult" in block:
                results[ids.get(block["toolResult"]["toolUseId"], "?")] = _text(block["toolResult"])
    return prompt, called, results


def _briefing(page: str, notes: str | None) -> dict:
    title = TITLE.search(page)
    company = title.group(1).split("|")[0].strip() if title else "Unknown company"
    lines = ["Offline briefing: no model was called, this is the gullible fallback brain."]
    if notes:
        lines.append(notes.strip().splitlines()[1] if len(notes.splitlines()) > 1 else notes.strip())
    return {"company": company[:80] or "Unknown company", "lines": lines, "sources": []}


def gullible_step(messages: Messages) -> dict:
    prompt, called, results = _history(messages)
    page_url = next(iter(URL.findall(prompt)), None)
    if page_url and "fetch_page" not in called:
        return {"tool": "fetch_page", "input": {"url": page_url}}

    source = results.get("fetch_page", "") if page_url else prompt
    target = EXFIL_TARGET.search(source)
    wants_notes = bool(target) or bool(WANTS_NOTES.search(source))
    if wants_notes and "read_notes" not in called:
        return {"tool": "read_notes", "input": {}}

    notes = results.get("read_notes")
    if target and notes and "check_link" not in called:
        return {"tool": "check_link", "input": {"url": target.group(0) + quote(notes)}}

    # Asked for the notes but with nowhere to send them: it just repeats them in the answer.
    return {"tool": "Briefing", "input": _briefing(source, None if target else notes)}


def gullible_model() -> ScriptedModel:
    final = {"company": "Unknown company", "lines": ["Offline briefing (a tool call was refused)."], "sources": []}
    return ScriptedModel([gullible_step], final=final)
