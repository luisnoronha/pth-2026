# backend

Thin AWS Lambda handlers. The logic lives in `strands/src/leash/hackrex/` (shared with the local server) and is tested in `strands/tests/hackrex/`.

| Handler | What |
|---|---|
| `api/handler.py` | behind API Gateway: `/api/...` goes to `leash.hackrex.api` (submit, poll, scoreboard, admin); every other path serves a page from a private S3 bucket. Loads only boto3 for pages, to keep cold starts short |
| `rex_lambda/handler.py` | runs Rex at leash level 5 for one attempt, judges it, stores the verdict |
| `webhook_board/handler.py` | the attacker's webhook (Lambda Function URL) and the board's feed (`/hits`) |

All three are packaged into one zip by `scripts/build_lambda.py` and deployed by `infra/terraform/`.
