variable "region" {
  description = "One EU region for everything."
  type        = string
  default     = "eu-north-1"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "hackrex"
}

variable "owner" {
  description = "Tag: who to ask about these resources."
  type        = string
  default     = "luis"
}

variable "delete_after" {
  description = "Tag: when this can all be destroyed."
  type        = string
  default     = "2026-11-17"
}

variable "lambda_zip" {
  description = "Built by scripts/build_lambda.py."
  type        = string
  default     = "../../build/lambda.zip"
}

# --- Rex ---------------------------------------------------------------------

variable "rex_model" {
  description = "Model name from strands/rex.yaml (haiku-4-5, haiku-5-5, gpt-mini)."
  type        = string
  default     = "haiku-4-5"
}

variable "rex_timeout_s" {
  description = "Rex's graceful timeout per attempt (seconds)."
  type        = number
  default     = 60
}

variable "rex_max_usd" {
  description = "Rex's cost budget per attempt (USD)."
  type        = number
  default     = 0.06
}

variable "rex_reserved_concurrency" {
  description = "Max Rex Lambdas at once (null = no reservation). Extra attacks wait in Lambda's async queue."
  type        = number
  default     = null
}

# --- Hack Rex limits ---------------------------------------------------------

variable "max_attempts" {
  description = "Total attempts accepted, then the game says it's full."
  type        = number
  default     = 1000
}

variable "attempts_per_player" {
  description = "Total attacks each player (phone) can send."
  type        = number
  default     = 3
}

variable "rate_per_minute" {
  description = "Attempts per minute per player (checked in the API Lambda)."
  type        = number
  default     = 5
}

variable "api_throttle_rate" {
  description = "API Gateway steady-state requests per second (all clients together)."
  type        = number
  default     = 100
}

variable "api_throttle_burst" {
  description = "API Gateway burst."
  type        = number
  default     = 200
}

variable "waf_requests_per_5min_per_ip" {
  description = "Flood guard per IP. High on purpose: the whole audience may share one venue wifi IP, and phones poll."
  type        = number
  default     = 20000
}
