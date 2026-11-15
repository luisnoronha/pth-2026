output "attack_url" {
  description = "Hack Rex attack page (share it as a QR code)."
  value       = "${local.site_url}/"
}

output "scoreboard_url" {
  description = "Scoreboard for a big screen. Space starts a 3:00 countdown."
  value       = "${local.site_url}/scoreboard.html"
}

output "admin_url" {
  value = "${local.site_url}/admin.html"
}

output "board_url" {
  description = "The attacker's webhook board: turns red when a secret arrives."
  value       = "${local.site_url}/board/index.html"
}

output "demo_page_url" {
  description = "Acme page with the hidden note. Use it in: rex --leash N \"Brief me on <this>\""
  value       = "${local.site_url}/demo/acme-ir.html"
}

output "demo_page_v2_url" {
  description = "The same note with three words changed."
  value       = "${local.site_url}/demo/acme-ir-v2.html"
}

output "webhook_url" {
  value = aws_lambda_function_url.webhook.function_url
}

output "laptop_env" {
  description = "To run Rex on your laptop against the deployed pages: run this in PowerShell first."
  value       = "$env:REX_EGRESS_ALLOWLIST = \"${local.site_host}\"; $env:REX_SOURCES_URL = \"${local.site_url}/demo/acme-q3.html\""
}

output "api_keys_secret" {
  description = "Secrets Manager secret for the model API keys. Fill it yourself (see infra/README.md); Terraform never sees them."
  value       = aws_secretsmanager_secret.api_keys.name
}

output "admin_token_command" {
  description = "Prints the /admin.html token."
  value       = "aws ssm get-parameter --name ${aws_ssm_parameter.admin_token.name} --with-decryption --query Parameter.Value --output text --region ${var.region}"
}

output "kill_switch_command" {
  description = "Close the game from a terminal (use \"open\" to reopen)."
  value       = "aws ssm put-parameter --name ${aws_ssm_parameter.switch.name} --value closed --overwrite --region ${var.region}"
}
