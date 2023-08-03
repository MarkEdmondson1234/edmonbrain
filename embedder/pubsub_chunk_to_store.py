# imports
import traceback

from langchain.docstore.document import Document
import base64
import json
import datetime

from langchain.schema import Document
import logging
from qna.llm import pick_llm
from qna.llm import pick_vectorstore

def from_pubsub_to_vectorstore(data: dict, vector_name:str):
    """Triggered from a message on a Cloud Pub/Sub topic "embed_chunk" topic
    Will only attempt to send one chunk to vectorstore.  For bigger documents use pubsub_to_store.py
    Args:
         data JSON
    """

    logging.debug(f"vectorstore: {vector_name}")

    #file_sha = data['message']['data']

    message_data = base64.b64decode(data['message']['data']).decode('utf-8')
    messageId = data['message'].get('messageId')
    publishTime = data['message'].get('publishTime')

    logging.debug(f"This Function was triggered by messageId {messageId} published at {publishTime}")
    logging.debug(f"from_pubsub_to_supabase message data: {message_data}")

    try:
        the_json = json.loads(message_data)
    except Exception as err:
        logging.error(f"Error - could not parse message_data: {err}: {message_data}")
        return "Could not parse message_data"

    if not isinstance(the_json, dict):
        raise ValueError(f"Could not parse message_data from json to a dict: got {message_data} or type: {type(the_json)}")

    page_content = the_json.get("page_content", None)
    if page_content is None:
        return "No page content"
    
    metadata = the_json.get("metadata", None)

    if 'eventTime' not in metadata:
        metadata['eventTime'] = datetime.datetime.utcnow().isoformat(timespec='microseconds') + "Z"


    doc = Document(page_content=page_content, metadata=metadata)

    # init embedding and vector store
    _, embeddings, _ = pick_llm(vector_name)
    vector_store = pick_vectorstore(vector_name, embeddings=embeddings)

    logging.debug("Adding single document to vector store")
    try:
        vector_store.add_documents([doc])
        logging.info(f"Added doc with metadata: {metadata}")
    except Exception as err:
        error_message = traceback.format_exc()
        logging.error(f"Could not add document {doc} to vector store: {str(err)} traceback: {error_message}")

    return metadata
