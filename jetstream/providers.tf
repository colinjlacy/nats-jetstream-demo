terraform {
  required_providers {
    jetstream = {
      source  = "nats-io/jetstream"
      version = "0.2.0"
    }
  }

  required_version = ">= 1.8.0"
}