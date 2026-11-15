# Three Lambdas from one zip (scripts/build_lambda.py):
#   api      fast: serves the pages; validates, stores, starts Rex, answers with an id (behind API Gateway)
#   rex      slow: run Rex at leash level 5, judge, store the verdict        (invoked async by api)
#   webhook  the attacker's endpoint + the board's feed                     (Function URL)
# Each has its own role with only what it needs.

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${local.name}-artifacts"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "lambda_zip" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "lambda-${filemd5(var.lambda_zip)}.zip"
  source = var.lambda_zip
}

locals {
  lambda_common = {
    runtime       = "python3.12"
    architectures = ["x86_64"]
    s3_bucket     = aws_s3_bucket.artifacts.id
    s3_key        = aws_s3_object.lambda_zip.key
    code_hash     = filebase64sha256(var.lambda_zip)
  }
  pages_base_url = "${local.site_url}/p"
  common_env = {
    REX_CONFIG     = "/var/task/rex.yaml"
    ATTEMPTS_TABLE = aws_dynamodb_table.attempts.name
    SITE_BUCKET    = aws_s3_bucket.site.id
    PAGES_BASE_URL = local.pages_base_url
  }
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# --- api ---------------------------------------------------------------------

resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "api" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Scan", "dynamodb:DeleteItem"]
    resources = [aws_dynamodb_table.attempts.arn]
  }
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.site.arn}/p/*"]
  }
  statement {
    actions   = ["ssm:GetParameter", "ssm:PutParameter"]
    resources = [aws_ssm_parameter.switch.arn]
  }
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.admin_token.arn]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }
  }
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.rex.arn, "${aws_lambda_function.rex.arn}:*"] # the function and its "live" alias
  }
  statement {
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [aws_bedrock_guardrail.moderation.guardrail_arn]
  }
}

resource "aws_iam_role_policy" "api" {
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 7
}

resource "aws_lambda_function" "api" {
  publish          = true # versions for the "live" alias (warm.tf)
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api.arn
  handler          = "api_handler.handler"
  runtime          = local.lambda_common.runtime
  architectures    = local.lambda_common.architectures
  s3_bucket        = local.lambda_common.s3_bucket
  s3_key           = local.lambda_common.s3_key
  source_code_hash = local.lambda_common.code_hash
  timeout          = 15
  memory_size      = 512

  environment {
    variables = merge(local.common_env, {
      SWITCH_PARAM                         = aws_ssm_parameter.switch.name
      ADMIN_TOKEN_PARAM                    = "${aws_ssm_parameter.admin_token.name}:${aws_ssm_parameter.admin_token.version}"
      REX_FUNCTION                         = "${aws_lambda_function.rex.function_name}:${local.alias}" # warm.tf
      HACKREX_MODERATION_GUARDRAIL_ID      = aws_bedrock_guardrail.moderation.guardrail_id
      HACKREX_MODERATION_GUARDRAIL_VERSION = "DRAFT"
      HACKREX_MAX_ATTEMPTS                 = tostring(var.max_attempts)
      HACKREX_RATE_PER_MINUTE              = tostring(var.rate_per_minute)
      HACKREX_ATTEMPTS_PER_PLAYER          = tostring(var.attempts_per_player)
    })
  }

  depends_on = [aws_cloudwatch_log_group.api, aws_iam_role_policy.api]
}

# --- rex ---------------------------------------------------------------------

resource "aws_iam_role" "rex" {
  name               = "${local.name}-rex"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "rex" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.rex.arn}:*"]
  }
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.attempts.arn]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.api_keys.arn]
  }
  statement {
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [aws_bedrock_guardrail.rex.guardrail_arn]
  }
}

resource "aws_iam_role_policy" "rex" {
  role   = aws_iam_role.rex.id
  policy = data.aws_iam_policy_document.rex.json
}

resource "aws_cloudwatch_log_group" "rex" {
  name              = "/aws/lambda/${local.name}-rex"
  retention_in_days = 7
}

resource "aws_lambda_function" "rex" {
  publish                        = true # versions for the "live" alias (warm.tf)
  function_name                  = "${local.name}-rex"
  role                           = aws_iam_role.rex.arn
  handler                        = "rex_handler.handler"
  runtime                        = local.lambda_common.runtime
  architectures                  = local.lambda_common.architectures
  s3_bucket                      = local.lambda_common.s3_bucket
  s3_key                         = local.lambda_common.s3_key
  source_code_hash               = local.lambda_common.code_hash
  timeout                        = 180 # Rex's own timeout is 60 s; the wallet win needs > 90 s
  memory_size                    = 512 # this account caps Lambda memory at 512 MB
  reserved_concurrent_executions = var.rex_reserved_concurrency

  environment {
    variables = merge(local.common_env, {
      API_KEYS_SECRET       = aws_secretsmanager_secret.api_keys.arn
      REX_MODEL             = var.rex_model
      REX_TIMEOUT_S         = tostring(var.rex_timeout_s)
      REX_MAX_USD           = tostring(var.rex_max_usd)
      REX_EGRESS_ALLOWLIST  = local.site_host
      REX_SOURCES_URL       = "${local.site_url}/demo/acme-q3.html"
      REX_GUARDRAIL_ID      = aws_bedrock_guardrail.rex.guardrail_id
      REX_GUARDRAIL_VERSION = "DRAFT"
    })
  }

  depends_on = [aws_cloudwatch_log_group.rex, aws_iam_role_policy.rex]
}

resource "aws_lambda_function_event_invoke_config" "rex" {
  function_name                = aws_lambda_function.rex.function_name
  qualifier                    = aws_lambda_alias.rex.name
  maximum_retry_attempts       = 0 # never run an attack twice
  maximum_event_age_in_seconds = 600
}

# --- webhook (the attacker's endpoint) ---------------------------------------

resource "aws_iam_role" "webhook" {
  name               = "${local.name}-webhook"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "webhook" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.webhook.arn}:*"]
  }
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:Scan"]
    resources = [aws_dynamodb_table.hits.arn]
  }
}

resource "aws_iam_role_policy" "webhook" {
  role   = aws_iam_role.webhook.id
  policy = data.aws_iam_policy_document.webhook.json
}

resource "aws_cloudwatch_log_group" "webhook" {
  name              = "/aws/lambda/${local.name}-webhook"
  retention_in_days = 7
}

resource "aws_lambda_function" "webhook" {
  function_name    = "${local.name}-webhook"
  role             = aws_iam_role.webhook.arn
  handler          = "webhook_handler.handler"
  runtime          = local.lambda_common.runtime
  architectures    = local.lambda_common.architectures
  s3_bucket        = local.lambda_common.s3_bucket
  s3_key           = local.lambda_common.s3_key
  source_code_hash = local.lambda_common.code_hash
  timeout          = 10
  memory_size      = 256

  environment {
    variables = { HITS_TABLE = aws_dynamodb_table.hits.name }
  }

  depends_on = [aws_cloudwatch_log_group.webhook, aws_iam_role_policy.webhook]
}

resource "aws_lambda_function_url" "webhook" {
  function_name      = aws_lambda_function.webhook.function_name
  authorization_type = "NONE" # it plays the attacker's public endpoint

  cors {
    allow_origins = ["*"]
    allow_methods = ["GET"]
  }
}

# Public function URLs need both permissions.
resource "aws_lambda_permission" "webhook_url" {
  statement_id           = "public-function-url"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.webhook.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "webhook_invoke" {
  statement_id             = "public-function-url-invoke"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.webhook.function_name
  principal                = "*"
  invoked_via_function_url = true
}
