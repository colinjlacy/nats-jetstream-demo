provider "jetstream" {
  # the domain of your cloud LB
  # or, if using OpenTofu, you can replace this with an early-evaluated variable
  # e.g. "${var.domain}"
  servers     = "k8s-default-natseast-d3a2cc2411-682b3011270d1d56.elb.us-east-1.amazonaws.com:4222"
  tls {
    ca_file = "./tls.ca"
    cert_file = "./tls.crt"
    key_file  = "./tls.key"
  }
}

resource "jetstream_stream" "answers" {
  name     = "answers"
  subjects = ["answers.significant", "answers.throwaway"]
  storage  = "file"
  max_age  = 60 * 60 * 24 * 365
}

# resource "jetstream_consumer" "ORDERS_NEW" {
#   stream_id      = jetstream_stream.ORDERS.id
#   durable_name   = "NEW"
#   deliver_all    = true
#   filter_subject = "ORDERS.received"
#   sample_freq    = 100
# }
