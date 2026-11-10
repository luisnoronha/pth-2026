output "attack_url" {
  description = "Hack Rex attack page (the QR code on S32)."
  value       = "${local.site_url}/"
}

output "scoreboard_url" {
  description = "Big screen (S32/S33). Space starts the 3:00 countdown."
  value       = "${local.site_url}/scoreboard.html"
}

output "admin_url" {
  value = "${local.site_url}/admin.html"
}

output "board_url" {
  description = "Demo 1 webhook board (right half of the screen)."
  value       = "${local.site_url}/board/index.html"
}

output "demo_page_url" {
  description = "Demo 1 poisoned page. Use it in: rex --leash N \"Brief me on <this>\""
  value       = "${local.site_url}/demo/acme-ir.html"
}

output "demo_page_v2_url" {
  value = "${local.site_url}/demo/acme-ir-v2.html"
}

output "webhook_url" {
  value = aws_lambda_function_url.webhook.function_url
}

output "laptop_env" {
  description = "For Demo 1 on the laptop against these pages: run this in PowerShell first."
  value       = "$env:REX_EGRESS_ALLOWLIST = \"${local.site_host}\"; $env:REX_SOURCES_URL = \"${local.site_url}/demo/acme-q3.html\""
}

output "admin_token_command" {
  description = "Prints the /admin.html token."
  value       = "aws ssm get-parameter --name ${aws_ssm_parameter.admin_token.name} --with-decryption --query Parameter.Value --output text --profile personal --region ${var.region}"
}

output "put_api_keys_command" {
  description = "Run this yourself with your real key(s). Terraform never sees them."
  value       = "aws secretsmanager put-secret-value --secret-id ${aws_secretsmanager_secret.api_keys.name} --secret-string '{\"ANTHROPIC_API_KEY\":\"sk-ant-...\",\"OPENAI_API_KEY\":\"sk-...\"}' --profile personal --region ${var.region}"
}

output "kill_switch_command" {
  description = "Close the game from a terminal (use \"open\" to reopen)."
  value       = "aws ssm put-parameter --name ${aws_ssm_parameter.switch.name} --value closed --overwrite --profile personal --region ${var.region}"
}
