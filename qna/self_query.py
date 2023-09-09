from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo

# example metadat
"""
{
  "type": "file_load_gcs",
  "attrs": "namespace:edmonbrain",
  "source": "gs://devoteam-mark-langchain-loader/edmonbrain/MarkWork/Running LLMs on Google Cloud Platform via Cloud Run, VertexAI and PubSub - LLMOps on GCP.md",
  "bucketId": "devoteam-mark-langchain-loader",
  "category": "NarrativeText",
  "filename": "Running LLMs on Google Cloud Platform via Cloud Run, VertexAI and PubSub - LLMOps on GCP.md",
  "filetype": "text/markdown",
  "objectId": "edmonbrain/MarkWork/Running LLMs on Google Cloud Platform via Cloud Run, VertexAI and PubSub - LLMOps on GCP.md",
  "eventTime": "2023-07-12T19:36:07.325740Z",
  "eventType": "OBJECT_FINALIZE",
  "bucket_name": "devoteam-mark-langchain-loader",
  "page_number": 1,
  "payloadFormat": "JSON_API_V1",
  "objectGeneration": "1689190567243818",
  "notificationConfig": "projects/_/buckets/devoteam-mark-langchain-loader/notificationConfigs/1"
}
"""

metadata_field_info = [
    AttributeInfo(
        name="source",
        description="The document source",
        type="string",
    ),
    AttributeInfo(
        name="eventTime",
        description="When this content was put into the memory",
        type="ISO 8601 formatted date and time string",
    ),
    AttributeInfo(
        name="type",
        description="How this content was added to the memory",
        type="string",
    ),
]
document_content_description = "Documents stored in the bot long term memory"

def get_self_query_retriever(llm, vectorstore):

    return SelfQueryRetriever.from_llm(
        llm, vectorstore, document_content_description, metadata_field_info, verbose=True
    )
