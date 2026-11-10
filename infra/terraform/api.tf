# REST API (not HTTP API: only REST supports WAF). Every path goes to the api Lambda, which
# serves both the pages and the game API. Every request is quick (pages, submit, poll,
# scoreboard), so the ~29 s API Gateway limit never bites.

resource "aws_api_gateway_rest_api" "hackrex" {
  name = "${local.name}-api"
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.hackrex.id
  parent_id   = aws_api_gateway_rest_api.hackrex.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.hackrex.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "proxy" {
  rest_api_id             = aws_api_gateway_rest_api.hackrex.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_alias.api.invoke_arn
}

# "/" itself is not covered by {proxy+}: the attack page needs its own route.
resource "aws_api_gateway_method" "root" {
  rest_api_id   = aws_api_gateway_rest_api.hackrex.id
  resource_id   = aws_api_gateway_rest_api.hackrex.root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "root" {
  rest_api_id             = aws_api_gateway_rest_api.hackrex.id
  resource_id             = aws_api_gateway_rest_api.hackrex.root_resource_id
  http_method             = aws_api_gateway_method.root.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_alias.api.invoke_arn
}

resource "aws_api_gateway_deployment" "hackrex" {
  rest_api_id = aws_api_gateway_rest_api.hackrex.id

  triggers = {
    redeploy = sha1(jsonencode([aws_api_gateway_resource.proxy.id, aws_api_gateway_method.proxy.id,
      aws_api_gateway_integration.proxy.id, aws_api_gateway_method.root.id, aws_api_gateway_integration.root.id,
    aws_api_gateway_integration.proxy.uri, aws_api_gateway_integration.root.uri]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "live" {
  rest_api_id   = aws_api_gateway_rest_api.hackrex.id
  deployment_id = aws_api_gateway_deployment.hackrex.id
  stage_name    = "live"
}

resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.hackrex.id
  stage_name  = aws_api_gateway_stage.live.stage_name
  method_path = "*/*"

  settings {
    throttling_rate_limit  = var.api_throttle_rate
    throttling_burst_limit = var.api_throttle_burst
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "api-gateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  qualifier     = aws_lambda_alias.api.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.hackrex.execution_arn}/*/*"
}

# --- WAF: a flood guard, not the game's rate limit ---------------------------
# The per-player limit lives in the api Lambda. Here: oversized bodies and floods per IP
# (with a high limit, since a whole room can share one wifi IP and phones poll).

resource "aws_wafv2_web_acl" "api" {
  name  = "${local.name}-api"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "body-too-large"
    priority = 1
    action {
      block {}
    }
    statement {
      size_constraint_statement {
        comparison_operator = "GT"
        size                = 8192
        field_to_match {
          body {
            oversize_handling = "MATCH"
          }
        }
        text_transformation {
          priority = 0
          type     = "NONE"
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "body-too-large"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "flood-per-ip"
    priority = 2
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = var.waf_requests_per_5min_per_ip
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "flood-per-ip"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-api"
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_api_gateway_stage.live.arn
  web_acl_arn  = aws_wafv2_web_acl.api.arn
}
