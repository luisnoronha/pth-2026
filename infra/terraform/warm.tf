# Cold starts. Three tools, all optional:
#   1. aliases: API Gateway and the api Lambda call the "live" alias of each function
#      (needed for provisioned concurrency; harmless otherwise)
#   2. keep_warm: a ping every 5 minutes, so one instance of each stays alive between visits
#   3. *_provisioned_concurrency: N instances always ready. Costs money while on:
#      turn it on before a live session, back to 0 after.

locals {
  alias = "live"
}

resource "aws_lambda_alias" "api" {
  name             = local.alias
  function_name    = aws_lambda_function.api.function_name
  function_version = aws_lambda_function.api.version
}

resource "aws_lambda_alias" "rex" {
  name             = local.alias
  function_name    = aws_lambda_function.rex.function_name
  function_version = aws_lambda_function.rex.version
}

resource "aws_lambda_provisioned_concurrency_config" "api" {
  count                             = var.api_provisioned_concurrency > 0 ? 1 : 0
  function_name                     = aws_lambda_function.api.function_name
  qualifier                         = aws_lambda_alias.api.name
  provisioned_concurrent_executions = var.api_provisioned_concurrency
}

resource "aws_lambda_provisioned_concurrency_config" "rex" {
  count                             = var.rex_provisioned_concurrency > 0 ? 1 : 0
  function_name                     = aws_lambda_function.rex.function_name
  qualifier                         = aws_lambda_alias.rex.name
  provisioned_concurrent_executions = var.rex_provisioned_concurrency
}

# --- keep-warm ping ----------------------------------------------------------

resource "aws_cloudwatch_event_rule" "keep_warm" {
  count               = var.keep_warm ? 1 : 0
  name                = "${local.name}-keep-warm"
  description         = "Ping the api and rex Lambdas so a visit doesn't wait for a cold start."
  schedule_expression = "rate(5 minutes)"
}

locals {
  warm_targets = var.keep_warm ? { api = aws_lambda_alias.api, rex = aws_lambda_alias.rex } : {}
}

resource "aws_cloudwatch_event_target" "keep_warm" {
  for_each = local.warm_targets
  rule     = aws_cloudwatch_event_rule.keep_warm[0].name
  arn      = each.value.arn
  input    = jsonencode({ warmup = true })
}

resource "aws_lambda_permission" "keep_warm" {
  for_each      = local.warm_targets
  statement_id  = "keep-warm"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  qualifier     = each.value.name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.keep_warm[0].arn
}
