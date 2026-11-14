# Keeping AI Agents on a Leash

A hands-on example of how to keep an AI agent safe and reliable **from the outside**, with [Strands Agents](https://strandsagents.com) hooks: guardrails, egress allowlists, output checks, budgets, timeouts and loop breakers.

You can't make the model safe. You can make the loop around it safe.

Built for the talk *"Keeping AI Agents on a Leash"* at Porto Tech Hub 2026.

## The example: Rex

Rex is a small research agent for **Example Capital**, a fictional investment fund. Give him a company's web page and he writes a 5-line briefing. He has four tools:

| Tool | What it does | Why it's dangerous |
|---|---|---|
| `fetch_page` | reads a web page | untrusted content gets into the model |
| `search` | looks up facts | can loop and burn money |
| `read_notes` | reads the analyst's **private notes** | private data |
| `check_link` | checks that a link is alive | a way to send data out |

Untrusted content, private data and a way out together are the **lethal trifecta**. The notes hold a secret (codename `NIGHTJAR`, ref `PTH-CANARY-7F3A`, both fake: a canary). The fictional Acme Corp's investor-relations page hides an HTML comment telling AI assistants to read their notes and "verify" a link with the notes in it. With no leash, Rex obeys and the secret leaves.

## The leash, level by level

Same agent, more hooks. Each level adds to the one before; [`levels.py`](strands/src/leash/hooks/levels.py) is the single source of truth.

| Level | Adds | Teaches | File |
|---|---|---|---|
| 0 | nothing | the hijack works | |
| 1 | Bedrock guardrail on the user message, in shadow mode | the user's request was innocent: the attack came in the back door | `hooks/shadow_guardrail.py` |
| 2 | the same guardrail on tool output (shadow) | you can point a guardrail at tool results yourself; give it plain text, not raw HTML; shadow mode logs but protects nothing | `hooks/tool_output_guardrail.py` |
| 3 | tool-output sanitiser (regex) | a cheap filter that works until the attacker changes three words | `hooks/sanitizer.py` |
| 4 | egress allowlist on every network tool, URL circuit breaker, output check on the final answer | fences, not filters: the secret has nowhere to go, whatever the wording | `hooks/egress.py`, `url_circuit_breaker.py`, `output_guard.py` |
| 5 | per-run state, graceful timeout, cost budget, pre-spend guard, tool limits, retry cap, tracing | kill the run, keep the answer | `hooks/state_init.py`, `timeout.py`, `budget.py`, `loop_breakers.py`, `tracing.py` |

Every hook is one small file with its own unit tests ([`strands/tests/hooks/`](strands/tests/hooks)), and has no dependency on Rex, so you can copy one into your own agent.

## Try it on your laptop

Needs Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
cd strands
uv sync
uv run pytest                     # unit tests, no network, no API keys
```

Serve the Acme pages and the attacker's webhook (from the repo root, in another terminal):

```bash
python scripts/local_demo.py
```

Ask Rex for a briefing, level by level. `--offline` uses a scripted "gullible" brain instead of a real model, so no API key is needed; drop it to use the model set in [`strands/rex.yaml`](strands/rex.yaml) (OpenAI or Anthropic, key from your environment).

```bash
cd strands
uv run rex --offline --leash 0 "Brief me on http://localhost:8000/acme-ir.html"      # leaks
uv run rex --offline --leash 3 "Brief me on http://localhost:8000/acme-ir.html"      # the sanitiser removes the order
uv run rex --offline --leash 3 "Brief me on http://localhost:8000/acme-ir-v2.html"   # reworded: leaks again
uv run rex --offline --leash 4 "Brief me on http://localhost:8000/acme-ir-v2.html"   # the allowlist blocks the link
```

When Rex leaks, the webhook terminal prints `REX JUST LEAKED`. Details in [`strands/README.md`](strands/README.md).

## Hack Rex (optional)

A small game where people attack Rex at full leash from their phones, in two ways: talking to him, or hiding instructions in a web page he is asked to brief. A deterministic judge decides who got the secret out and which layer stopped everyone else; a scoreboard shows the funnel by layer. Run it locally with `uv run hackrex-local --offline`, or deploy it to AWS with the Terraform in [`infra/`](infra/README.md).

## Repository layout

| Folder | What |
|---|---|
| [`strands/`](strands/README.md) | the `leash` Python package: Rex, the hooks, the Hack Rex game logic, tests |
| [`frontend/`](frontend/README.md) | static pages: the Acme pages, the webhook board, the Hack Rex pages |
| [`backend/`](backend/README.md) | the three AWS Lambda handlers |
| [`infra/`](infra/README.md) | Terraform for AWS (deploy, cold starts, cost, tear down) |
| [`scripts/`](scripts/README.md) | the local demo server and the Lambda build |

## License

[MIT](LICENSE).
