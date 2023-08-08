# Chunker

Processes documents into chunks and sends then to the encoder

Destination for PubSub Cloud Storage topic

## Batch

Setup so failures to normal endpoint get dead-letter sent to a new PubSub topic taht will send to Google Batch