/* This parses the raw data from the PubSub topic into a nested BigQuery table view */
SELECT 
  JSON_VALUE(SAFE.PARSE_JSON(data), "$.vector_name") as vector_name,
  JSON_VALUE(SAFE.PARSE_JSON(data), "$.bot_output.question") as question,
  JSON_VALUE(SAFE.PARSE_JSON(data), "$.bot_output.answer") as bot_output,
  JSON_VALUE(SAFE.PARSE_JSON(data), "$.timestamp") as created_timestamp,
  JSON_QUERY(SAFE.PARSE_JSON(data), "$.bot_output.chat_history") as chat_history,
  ARRAY(
    SELECT STRUCT(
      JSON_VALUE(source_document, "$.metadata.source") as source,
      JSON_VALUE(source_document, "$.metadata.type") as load_type,
      JSON_VALUE(source_document, "$.metadata.eventTime") as eventTime,
      JSON_VALUE(source_document, "$.metadata.bucketId") as bucketId,
      
      JSON_VALUE(source_document, "$.metadata.category") as load_category,
      JSON_VALUE(source_document, "$.metadata.page_number") as page_number,
      /* Include more fields here... */
      JSON_QUERY(source_document, "$.page_content") as page_content,
      source_document as full_source_document
    )
    FROM UNNEST(JSON_EXTRACT_ARRAY(SAFE.PARSE_JSON(data), "$.bot_output.source_documents")) as source_document
  ) as source_documents,
  SAFE.PARSE_JSON(data) as data_json,
  subscription_name,
  message_id,
  publish_time,
  attributes
FROM  `langchain.pubsub_raw`
WHERE DATE(publish_time) > "2023-07-13"
AND SAFE.PARSE_JSON(data) IS NOT NULL
ORDER BY created_timestamp DESC
