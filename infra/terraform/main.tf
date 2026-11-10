# Hack Rex + Demo 1 on AWS. One root, one file per concern:
#   site.tf        private S3 bucket with the pages (served by the api Lambda)
#   data.tf        DynamoDB: attempts (Hack Rex) and hits (Demo 1 webhook)
#   config.tf      Secrets Manager (model API keys), SSM (kill switch, admin token)
#   guardrails.tf  Bedrock Guardrails: Rex (prompt attack, shadow) and moderation
#   lambdas.tf     api (site + API), rex and webhook Lambdas + IAM
#   api.tf         API Gateway (REST) + WAF: the one public https address
#   outputs.tf     URLs and the commands you need

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name = "${var.project}-${random_id.suffix.hex}"
  repo = abspath("${path.module}/../..")
  # Built from the API id (not the stage) so the Lambdas can know it without a dependency cycle.
  site_host = "${aws_api_gateway_rest_api.hackrex.id}.execute-api.${var.region}.amazonaws.com"
  site_url  = "https://${local.site_host}/live"
}
