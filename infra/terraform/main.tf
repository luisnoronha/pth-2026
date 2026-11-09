# Hack Rex + Demo 1 on AWS. One root, one file per concern:
#   site.tf        S3 + CloudFront: attack page, scoreboard, admin, Demo 1 board and pages, poisoned pages
#   data.tf        DynamoDB: attempts (Hack Rex) and hits (Demo 1 webhook)
#   config.tf      Secrets Manager (model API keys), SSM (kill switch, admin token)
#   guardrails.tf  Bedrock Guardrails: Rex (prompt attack, shadow) and moderation
#   lambdas.tf     api, rex and webhook Lambdas + IAM
#   api.tf         API Gateway (REST) + WAF
#   outputs.tf     URLs and the commands you need

data "aws_caller_identity" "current" {}

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name       = "${var.project}-${random_id.suffix.hex}"
  account_id = data.aws_caller_identity.current.account_id
  repo       = abspath("${path.module}/../..")
  site_url   = "https://${aws_cloudfront_distribution.site.domain_name}"
  api_url    = aws_api_gateway_stage.live.invoke_url
}
