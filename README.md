# pth-2026

Code for the talk **"Keeping AI Agents on a Leash"** (Porto Tech Hub 2026): Rex, a research agent built to be hijacked, the Strands hooks that keep him on a leash, and Hack Rex, a live game where the audience attacks him.

## Live URLs (until the stack is destroyed after the event)

| What | URL | Who opens it |
|---|---|---|
| Hack Rex attack page (QR on S32) | https://bqai7qv3bl.execute-api.eu-north-1.amazonaws.com/live/ | the audience, on phones |
| Scoreboard (S32/S33) | https://bqai7qv3bl.execute-api.eu-north-1.amazonaws.com/live/scoreboard.html | the big screen (Space starts the 3:00 round) |
| Admin | https://bqai7qv3bl.execute-api.eu-north-1.amazonaws.com/live/admin.html | the speaker only (needs the admin token) |
| Demo 1 webhook board | https://bqai7qv3bl.execute-api.eu-north-1.amazonaws.com/live/board/index.html | the big screen, right half, during Demo 1 |
| Demo 1 poisoned page (v1) | https://bqai7qv3bl.execute-api.eu-north-1.amazonaws.com/live/demo/acme-ir.html | Rex, from the laptop CLI |
| Demo 1 poisoned page (v2, level 3b) | https://bqai7qv3bl.execute-api.eu-north-1.amazonaws.com/live/demo/acme-ir-v2.html | Rex, from the laptop CLI |

Everything is one address: the pages and the game API (`/live/api/...`) are served by the same Lambda behind API Gateway. The Demo 1 webhook (the "attacker's server") is a separate Lambda URL on purpose, so the egress fence can block it. All URLs and commands are also printed by `terraform output` in `infra/terraform`.

## Where things are

| Folder | What |
|---|---|
| [`strands/`](strands/README.md) | the `leash` Python package: Rex, the hooks per level, Hack Rex logic, tests |
| [`frontend/`](frontend/README.md) | static pages: Hack Rex, Demo 1 board and poisoned pages |
| [`backend/`](backend/README.md) | the three Lambda handlers |
| [`infra/`](infra/README.md) | Terraform (deploy, update, destroy) |
| `scripts/` | local Demo 1 server, Lambda zip build |
