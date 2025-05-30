
variable "nats_servers" {
  description = "The NATS server address"
  type        = string
}
variable "nats_tls_ca_file" {
  description = "The CA file for NATS TLS"
  type        = string
}
variable "nats_tls_cert_file" {
  description = "The certificate file for NATS TLS"
  type        = string
}
variable "nats_tls_key_file" {
  description = "The key file for NATS TLS"
  type        = string
}

terraform {
  required_providers {
    jetstream = {
      source  = "nats-io/jetstream"
      version = "0.2.0"
    }
  }

  required_version = ">= 1.8.0"
}

provider "jetstream" {
  # the domain of your cloud LB
  servers     = var.nats_servers
  tls {
    ca_file = var.nats_tls_ca_file
    cert_file = var.nats_tls_cert_file
    key_file  = var.nats_tls_key_file
  }
}