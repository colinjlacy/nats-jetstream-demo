
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
