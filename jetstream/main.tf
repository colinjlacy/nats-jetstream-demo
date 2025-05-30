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

provider "jetstream" {
  # the domain of your cloud LB
  servers     = var.nats_servers
  tls {
    ca_file = var.nats_tls_ca_file
    cert_file = var.nats_tls_cert_file
    key_file  = var.nats_tls_key_file
  }
}

resource "jetstream_stream" "answers" {
  name     = "answers"
  subjects = ["answers.significant", "answers.throwaway"]
  storage  = "file"
  # max_bytes  = 1028
  # max_msgs   = 30
  # max_age  = 20
  # duplicate_window = 10
  # max_age  = 60 * 60 * 24 * 5
}

# resource "jetstream_consumer" "recorder" {
#   stream_id      = jetstream_stream.answers.id
#   durable_name   = "answers-consumer"
#   deliver_all    = true
#   filter_subjects = ["answers.significant"]
#   sample_freq    = 100
# }
