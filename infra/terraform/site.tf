# The site's files live in one private bucket; the api Lambda serves them through
# API Gateway, so the whole game is one https address (see backend/api/handler.py).
#   /index.html, /scoreboard.html, /admin.html   Hack Rex (frontend/web)
#   /board/index.html                            attacker webhook board (frontend/board)
#   /demo/acme-ir.html, /demo/acme-ir-v2.html    Acme pages with the hidden note
#   /demo/acme-q3.html                           clean page Rex's search results cite
#   /p/<id>.html                                 "Poison the page" attempts (written by the api Lambda)
#   /config.js                                   API and webhook URLs for the pages
# Rex's egress allowlist is this API Gateway host only.
# (No CloudFront: new accounts need AWS Support to verify them before creating distributions.)

resource "aws_s3_bucket" "site" {
  bucket        = "${local.name}-site"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    id     = "expire-poisoned-pages"
    status = "Enabled"
    filter {
      prefix = "p/"
    }
    expiration {
      days = 7
    }
  }
}

locals {
  # The Acme pages point at the local webhook; on AWS they point at the webhook Lambda.
  webhook_c_url = "${aws_lambda_function_url.webhook.function_url}c?d="

  static_files = {
    "index.html"       = "${local.repo}/frontend/web/index.html"
    "scoreboard.html"  = "${local.repo}/frontend/web/scoreboard.html"
    "admin.html"       = "${local.repo}/frontend/web/admin.html"
    "board/index.html" = "${local.repo}/frontend/board/index.html"
  }
  demo_pages = {
    "demo/acme-ir.html"    = "${local.repo}/frontend/demo_pages/acme-ir.html"
    "demo/acme-ir-v2.html" = "${local.repo}/frontend/demo_pages/acme-ir-v2.html"
    "demo/acme-q3.html"    = "${local.repo}/frontend/demo_pages/acme-q3.html"
  }
}

resource "aws_s3_object" "static" {
  for_each     = local.static_files
  bucket       = aws_s3_bucket.site.id
  key          = each.key
  source       = each.value
  etag         = filemd5(each.value)
  content_type = "text/html; charset=utf-8"
}

resource "aws_s3_object" "demo_pages" {
  for_each     = local.demo_pages
  bucket       = aws_s3_bucket.site.id
  key          = each.key
  content      = replace(file(each.value), "http://localhost:8001/c?d=", local.webhook_c_url)
  content_type = "text/html; charset=utf-8"
}

resource "aws_s3_object" "config_js" {
  bucket       = aws_s3_bucket.site.id
  key          = "config.js"
  content      = "window.HACKREX_API = ${jsonencode(local.site_url)};\nwindow.WEBHOOK_URL = ${jsonencode(aws_lambda_function_url.webhook.function_url)};\n"
  content_type = "application/javascript"
}
