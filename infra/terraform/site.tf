# One private bucket behind one CloudFront distribution (https, no public bucket).
#   /index.html, /scoreboard.html, /admin.html   Hack Rex (frontend/web)
#   /board/index.html                            Demo 1 webhook board (frontend/board)
#   /demo/acme-ir.html, /demo/acme-ir-v2.html    Demo 1 poisoned pages
#   /p/<id>.html                                 "Poison the page" attempts (written by the API Lambda)
#   /config.js                                   API and webhook URLs for the pages
# Rex's egress allowlist is this CloudFront domain (+ example.com).

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

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${local.name}-site"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled" # pages change during the game; nothing here is heavy
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  comment             = "${local.name} Hack Rex + Demo 1"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    origin_id                = "site"
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id       = "site"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.disabled.id
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "site" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket     = aws_s3_bucket.site.id
  policy     = data.aws_iam_policy_document.site.json
  depends_on = [aws_s3_bucket_public_access_block.site]
}

# --- Files ------------------------------------------------------------------

locals {
  # The Demo 1 pages point at the local webhook; on AWS they point at the webhook Lambda.
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
  }
}

resource "aws_s3_object" "static" {
  for_each      = local.static_files
  bucket        = aws_s3_bucket.site.id
  key           = each.key
  source        = each.value
  etag          = filemd5(each.value)
  content_type  = "text/html; charset=utf-8"
  cache_control = "no-store"
}

resource "aws_s3_object" "demo_pages" {
  for_each      = local.demo_pages
  bucket        = aws_s3_bucket.site.id
  key           = each.key
  content       = replace(file(each.value), "http://localhost:8001/c?d=", local.webhook_c_url)
  content_type  = "text/html; charset=utf-8"
  cache_control = "no-store"
}

resource "aws_s3_object" "config_js" {
  bucket        = aws_s3_bucket.site.id
  key           = "config.js"
  content       = "window.HACKREX_API = ${jsonencode(trimsuffix(local.api_url, "/"))};\nwindow.WEBHOOK_URL = ${jsonencode(aws_lambda_function_url.webhook.function_url)};\n"
  content_type  = "application/javascript"
  cache_control = "no-store"
}
