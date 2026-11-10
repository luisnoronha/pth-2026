terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local state is fine for a one-person, one-off demo. Keep terraform.tfstate out of git.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project      = var.project
      owner        = var.owner
      event        = "porto-tech-hub-2026"
      delete_after = var.delete_after
      managed_by   = "terraform"
    }
  }
}
