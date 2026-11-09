# backend

Thin Lambda handlers. The logic lives in `strands/src/leash/hackrex/` (shared with the local server) and is tested in `strands/tests/hackrex/`.

- `api/handler.py`: API Gateway proxy -> `leash.hackrex.api` (submit, poll, scoreboard, admin)
- `rex_lambda/handler.py`: runs Rex (level 5) for one attempt id, judges it, stores the verdict
- `webhook_board/handler.py`: Demo 1 attacker's webhook (Function URL) + the board's feed

Packaged together by `scripts/build_lambda.py` into `build/lambda.zip`. Deployed by `infra/terraform/`.
