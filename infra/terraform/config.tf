# Model API keys: Terraform creates an EMPTY secret ("{}"). You put the real keys
# in yourself (see the `put_api_keys` output); Terraform never sees or overwrites them.
resource "aws_secretsmanager_secret" "api_keys" {
  name                    = "${local.name}/model-api-keys"
  recovery_window_in_days = 0 # destroy really deletes it
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id     = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({ ANTHROPIC_API_KEY = "", OPENAI_API_KEY = "" })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Kill switch: "open" or "closed". Flipped from /admin.html (or the CLI).
resource "aws_ssm_parameter" "switch" {
  name  = "/${local.name}/open"
  type  = "String"
  value = "open"

  lifecycle {
    ignore_changes = [value]
  }
}

# Initial admin token for /admin.html. Rotate it in Parameter Store, then apply
# Terraform to publish the API Lambda with the new parameter version.
resource "random_password" "admin_token" {
  length  = 20
  special = false
}

resource "aws_ssm_parameter" "admin_token" {
  name  = "/${local.name}/admin-token"
  type  = "SecureString"
  value = random_password.admin_token.result

  lifecycle {
    ignore_changes = [value]
  }
}
