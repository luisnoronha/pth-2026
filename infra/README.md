# infra

Terraform for Hack Rex and Demo 1 on AWS (`eu-north-1`), in `terraform/`. One root, one file per concern (see `terraform/main.tf`).

## What gets created

| Piece | AWS |
|---|---|
| Attack page, scoreboard, admin, Demo 1 board and pages, poisoned pages (`/p/`) | S3 (private) + CloudFront |
| API (submit, poll, scoreboard, admin) | API Gateway (REST) + WAF + `api` Lambda |
| Rex at leash level 5, one run per attack | `rex` Lambda (async, no retries) |
| Attempts / Demo 1 webhook hits | DynamoDB on-demand, auto-delete after 7 days |
| Model API keys | Secrets Manager (created empty; you fill it) |
| Kill switch, admin token | SSM parameters |
| Rex guardrail (shadow) + moderation guardrail | Bedrock Guardrails |
| Demo 1 attacker's webhook | `webhook` Lambda + Function URL |

No AgentCore and no Bedrock models: Rex runs in Lambda and calls the Anthropic / OpenAI API.

## Deploy

From the repo root, with `aws sso login --profile personal` done:

```bash
uv run --project strands python scripts/build_lambda.py
```

```bash
cd infra/terraform
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

Then, once:

1. Put the model API key(s) in the secret: run the `put_api_keys_command` output with your real key(s).
2. Get the admin token: `admin_token_command` output.
3. Open `attack_url`, `scoreboard_url`, `admin_url`.

Set `AWS_PROFILE=personal` (or `--profile`) for the Terraform commands.

## Tear down

```bash
terraform destroy
```

Everything goes, including the secret (no recovery window) and the buckets (force destroy). Your AWS access (IAM Identity Center) is not managed here.

## Cost (rough, [verify])

- Fixed: WAF ~$7/month (prorated hourly), Secrets Manager $0.40/month.
- Per use: Lambda, API Gateway, DynamoDB, S3, CloudFront: cents for a few hundred attacks.
- Guardrails: billed per 1,000 characters checked; Rex's guardrail reads every page it fetches. Roughly $0.004 per attack.
- The model API (Anthropic / OpenAI) is billed on your API account: ~$0.01–0.03 per attack.
