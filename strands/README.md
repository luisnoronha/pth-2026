# leash: Rex and the hooks

The Python package: Rex (the agent), the Strands hooks for each leash level, and the Hack Rex game logic.

```bash
uv sync                      # .venv with Python 3.12 and pinned dependencies
uv run pytest                # unit tests (tests that call a real model are skipped)
uv run pytest -m e2e -s      # the attack ladder with a real model (costs a few cents)
```

## Run Rex

Terminal 1, from the repo root: the Acme pages on port 8000 and the attacker's webhook on 8001.

```bash
python scripts/local_demo.py
```

Terminal 2, from `strands/`:

```bash
uv run rex --leash 0 "Brief me on http://localhost:8000/acme-ir.html"
```

Rex's tool calls are printed in colour. If he leaks, terminal 1 prints `REX JUST LEAKED: ...`. The page and the webhook are on different ports on purpose: the egress allowlist (level 4) allows the page's `host:port` and not the webhook's.

Pages in `frontend/demo_pages/`:

| Page | What |
|---|---|
| `acme-ir.html` | Acme's results page with a hidden note for AI assistants (caught by the sanitiser) |
| `acme-ir-v2.html` | the same note with three words changed (passes the sanitiser) |
| `acme-q3.html` | a clean fact sheet; Rex's search results cite it |

### No API key: `--offline`

`--offline` swaps the model for a scripted "gullible" brain that obeys whatever instruction it can read. Same tools, same hooks, so the leash behaves as with a real model: level 3 removes the order, the reworded page gets past the sanitiser, level 4 blocks the link.

```bash
uv run rex --offline --leash 3 "Brief me on http://localhost:8000/acme-ir-v2.html"
```

## Choosing the model

[`rex.yaml`](rex.yaml) lists the models; `active` is the default and `--model <name>` overrides it for one run.

| Provider | Credentials (from your environment, never from the repo) |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |

```bash
uv run rex --model gpt-mini --leash 0 "Brief me on http://localhost:8000/acme-ir.html"
```

Levels 1 and 2 also need a Bedrock guardrail and AWS credentials: set `REX_GUARDRAIL_ID` (and `REX_GUARDRAIL_VERSION`, default `DRAFT`). Without one, those hooks log a warning and do nothing. `infra/terraform/guardrails.tf` creates one.

## Leash levels

`--leash 0` … `--leash 5`. Levels are cumulative; [`src/leash/hooks/levels.py`](src/leash/hooks/levels.py) is the single source of truth, in run order.

| Level | Adds | File (`src/leash/hooks/`) |
|---|---|---|
| 1 | Shadow guardrail on the user message | `shadow_guardrail.py` |
| 2 | Shadow guardrail on tool output (sent as plain text) | `tool_output_guardrail.py` |
| 3 | Tool-output sanitiser | `sanitizer.py` |
| 4 | Egress allowlist on every network tool, URL circuit breaker, output check on the final answer | `egress.py`, `url_circuit_breaker.py`, `output_guard.py` |
| 5 | State init, graceful timeout, cost budget, pre-spend guard, tool limits, output retry cap, tracing | `state_init.py`, `timeout.py`, `budget.py`, `loop_breakers.py`, `tracing.py` |

Settings (environment variables, defaults in brackets): `REX_TIMEOUT_S` (60), `REX_MAX_USD` (0.06), `REX_MAX_INPUT_TOKENS` (50000), `REX_EGRESS_ALLOWLIST` (`localhost:8000`), `REX_SOURCES_URL`.

## Hack Rex on your laptop

```bash
uv run hackrex-local --offline        # drop --offline to use the real model
```

Attack page on `http://localhost:8000/`, scoreboard on `/scoreboard` (Space starts a 3:00 countdown), admin on `/admin` (token printed at start-up: approve snippets for the scoreboard, open or close the game). Rex always runs at leash level 5. Code in `src/leash/hackrex/`, pages in `frontend/web/`. Attempts are kept in `scripts/.hackrex/` (git-ignored).

Settings: `HACKREX_ADMIN_TOKEN`, `HACKREX_MODERATION_GUARDRAIL_ID`, `HACKREX_WALLET_SLACK` (1.5), `HACKREX_RATE_PER_MINUTE` (5), `HACKREX_ATTEMPTS_PER_PLAYER` (3), `HACKREX_MAX_ATTEMPTS` (1000).

Pinned versions: strands-agents 1.64.0, boto3 1.43.126, Python 3.12.
