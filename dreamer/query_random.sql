SELECT 
  JSON_VALUE(SAFE.PARSE_JSON(data), "$.bot_output.question") as question,
  JSON_VALUE(SAFE.PARSE_JSON(data), "$.bot_output.answer") as bot_output,
  JSON_QUERY(SAFE.PARSE_JSON(data), "$.bot_output.chat_history") as chat_history,
  ARRAY(
    SELECT JSON_QUERY(source_document, "$.page_content") as page_content
    FROM UNNEST(JSON_EXTRACT_ARRAY(SAFE.PARSE_JSON(data), "$.bot_output.source_documents")) as source_document
  ) as source_documents_page_contents
FROM  `langchain.pubsub_raw`
WHERE DATE(publish_time) != "{date}"
AND SAFE.PARSE_JSON(data) IS NOT NULL
ORDER BY RAND()
LIMIT {limit}
