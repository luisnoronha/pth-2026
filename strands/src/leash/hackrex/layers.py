"""The scoreboard's funnel layers. Kept free of heavy imports: the API Lambda that
serves pages and the scoreboard loads this without loading Strands or the model SDKs."""

# Funnel order on the scoreboard: strongest fence first.
LAYERS = ["fence", "output", "limits", "sanitizer", "guardrail", "model"]
LABELS = {
    "fence": "Blocked at the fence",
    "output": "Output check",
    "limits": "Budget / timeout / loop limits",
    "sanitizer": "Sanitiser",
    "guardrail": "Guardrail (flagged, shadow)",
    "model": "Rex didn't fall for it",
    "got_through": "Got through",
}
