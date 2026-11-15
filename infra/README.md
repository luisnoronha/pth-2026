# infra

Terraform for the Hack Rex game and the attack demo on AWS, in `terraform/`. One root module, one file per concern (see `terraform/main.tf`). Default region: `eu-north-1`.

## What gets created

| Piece | AWS |
|---|---|
| One https address for everything: attack page, scoreboard, admin, webhook board, the Acme pages, pages written by players (`/p/`) and the game API | API Gateway (REST) + WAF + `api` Lambda, pages kept in a private S3 bucket |
| Rex at leash level 5, one run per attack | `rex` Lambda (invoked asynchronously, no retries) |
| Attempts, webhook hits | DynamoDB on-demand, items expire after 7 days |
| Model API keys | Secrets Manager (created empty; you fill it) |
| Kill switch, admin token | SSM parameters |
| Rex's guardrail (prompt attack, shadow) + moderation guardrail | Bedrock Guardrails |
| The attacker's webhook | `webhook` Lambda + Function URL (a different host, so the allowlist blocks it) |
| Cold starts | `live` aliases, a keep-warm ping, optional provisioned concurrency (`warm.tf`) |

Rex's model comes from the Anthropic or OpenAI API (`strands/rex.yaml`), so no Bedrock model access is needed. No CloudFront: the api Lambda serves the pages.

## Deploy

Needs AWS credentials for the target account (e.g. `aws sso login` and `AWS_PROFILE`), Terraform ≥ 1.9 and `uv`. From the repo root:

```bash
uv run --project strands python scripts/build_lambda.py
cd infra/terraform
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

Then:

1. Put the model API key(s) in the secret (`api_keys_secret` output). Write the JSON to a file and pass it with `file://`, so the key never sits in your shell history:
   ```bash
   aws secretsmanager put-secret-value --secret-id <api_keys_secret> --secret-string file://keys.json
   ```
   with `keys.json` = `{"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "sk-..."}`. Delete the file afterwards. If you only have an OpenAI key, set `rex_model = "gpt-mini"` in `terraform.tfvars`.
2. Get the admin token: the `admin_token_command` output.
3. Open `attack_url`, `scoreboard_url`, `admin_url`.

Settings live in `variables.tf`; override them in `terraform.tfvars` (git-ignored, see `terraform.tfvars.example`).

Frontend change: `terraform apply`. Code or `rex.yaml` change: `scripts/build_lambda.py`, then `terraform apply`.

## Cold starts

The first request after a quiet spell waits for a Lambda to start. In `warm.tf`:

- The api Lambda serves pages with boto3 only; Rex and the model SDKs load only in the rex Lambda.
- `keep_warm` (default on): a ping every 5 minutes keeps one instance of each Lambda alive.
- `api_provisioned_concurrency` / `rex_provisioned_concurrency` (default 0): instances always ready. Turn them on for a live session and back to 0 after; they cost a few cents per hour while on.

New AWS accounts can have low limits (e.g. 512 MB per Lambda, no CloudFront until AWS Support verifies the account).

## Tear down

```bash
terraform destroy
```

Everything goes, including the secret (no recovery window) and the buckets (force destroy). Your own AWS access is not managed here.

## Cost (rough)

- Fixed: WAF ~$7/month (prorated hourly), Secrets Manager $0.40/month.
- Per use: Lambda, API Gateway, DynamoDB, S3: cents for a few hundred attacks.
- Guardrails: billed per 1,000 characters checked; Rex's guardrail reads every page it fetches.
- The model API is billed on your Anthropic / OpenAI account: about $0.002 per attack with `gpt-5-mini` at minimal reasoning.
