# Rex's guardrail (leash levels 1-2): the prompt-attack filter, used in SHADOW mode
# by the hooks (ApplyGuardrail, log "would block", never block).
resource "aws_bedrock_guardrail" "rex" {
  name                      = "${local.name}-rex"
  description               = "Rex prompt-attack filter, evaluated in shadow mode by the leash hooks."
  blocked_input_messaging   = "Blocked by the guardrail."
  blocked_outputs_messaging = "Blocked by the guardrail."

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }
}

# Moderation for Hack Rex submissions: abusive text is rejected and never stored.
resource "aws_bedrock_guardrail" "moderation" {
  name                      = "${local.name}-moderation"
  description               = "Hack Rex: reject abusive submissions before anything is stored."
  blocked_input_messaging   = "Be nice."
  blocked_outputs_messaging = "Be nice."

  content_policy_config {
    dynamic "filters_config" {
      for_each = ["HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT"]
      content {
        type            = filters_config.value
        input_strength  = "MEDIUM"
        output_strength = "NONE"
      }
    }
  }
}
