# imports
import os, json, re, sys
import pathlib

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from google.cloud import storage
import base64
import datetime
import logging
from dotenv import load_dotenv
import tempfile
import hashlib

import langchain.text_splitter as text_splitter
from langchain.schema import Document

from qna.pubsub_manager import PubSubManager
import qna.database as database
import qna.loaders as loaders
from qna.pdfs import split_pdf_to_pages

load_dotenv()

def contains_url(message_data):
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    if url_pattern.search(message_data):
        return True
    else:
        return False

def extract_urls(text):
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    urls = url_pattern.findall(text)
    return urls

def compute_sha1_from_file(file_path):
    with open(file_path, "rb") as file:
        bytes = file.read() 
        readable_hash = hashlib.sha1(bytes).hexdigest()
    return readable_hash

def compute_sha1_from_content(content):
    readable_hash = hashlib.sha1(content).hexdigest()
    return readable_hash

def add_file_to_gcs(filename: str, vector_name:str, bucket_name: str=None, metadata:dict=None):

    storage_client = storage.Client()

    bucket_name = bucket_name if bucket_name is not None else os.getenv('GCS_BUCKET', None)
    if bucket_name is None:
        raise ValueError("No bucket found to upload to: GCS_BUCKET returned None")
    
    if bucket_name.startswith("gs://"):
        bucket_name = bucket_name.removeprefix("gs://")
    
    logging.info(f"Bucket_name: {bucket_name}")
    bucket = storage_client.get_bucket(bucket_name)
    now = datetime.datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d") 
    hour = now.strftime("%H")
    hour_prev = (now - datetime.timedelta(hours=1)).strftime("%H")

    bucket_filepath = f"{vector_name}/{year}/{month}/{day}/{hour}/{os.path.basename(filename)}"
    bucket_filepath_prev = f"{vector_name}/{year}/{month}/{day}/{hour_prev}/{os.path.basename(filename)}"

    blob = bucket.blob(bucket_filepath)
    blob_prev = bucket.blob(bucket_filepath_prev)

    if blob.exists():
        logging.info(f"File {filename} already exists in gs://{bucket_name}/{bucket_filepath}")
        return f"gs://{bucket_name}/{bucket_filepath}"

    if blob_prev.exists():
        logging.info(f"File {filename} already exists in gs://{bucket_name}/{bucket_filepath_prev}")
        return f"gs://{bucket_name}/{bucket_filepath_prev}"

    logging.info(f"File {filename} does not already exist in bucket {bucket_name}/{bucket_filepath}")

    the_metadata = {
        "vector_name": vector_name,
    }
    if metadata is not None:
        the_metadata.update(metadata)

    blob.metadata = the_metadata

    blob.upload_from_filename(filename)

    logging.info(f"File {filename} uploaded to gs://{bucket_name}/{bucket_filepath}")

    # create pubsub topic and subscription if necessary to receive notifications from cloud storage 
    pubsub_manager = PubSubManager(vector_name, pubsub_topic=f"app_to_pubsub_{vector_name}")
    sub_name = f"pubsub_to_store_{vector_name}"
    sub_exists = pubsub_manager.subscription_exists(sub_name)
    if not sub_exists:
        pubsub_manager.create_subscription(sub_name,
                                           push_endpoint=f"/pubsub_to_store/{vector_name}")
        database.setup_database(vector_name)
        

    return f"gs://{bucket_name}/{bucket_filepath}"

def choose_splitter(extension: str, chunk_size: int=1024, chunk_overlap:int=0):
    if extension == ".py":
        return text_splitter.PythonCodeTextSplitter()
    elif extension == ".md":
        return text_splitter.MarkdownTextSplitter()
    
    return text_splitter.RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

def remove_whitespace(page_content: str):
    return page_content.replace("\n", " ").replace("\r", " ").replace("\t", " ").replace("  ", " ")


def chunk_doc_to_docs(documents: list, extension: str = ".md"):
    """Turns a Document object into a list of many Document chunks"""
    if documents is None:
        return None
    
    source_chunks = []
    for document in documents:
        splitter = choose_splitter(extension)
        for chunk in splitter.split_text(remove_whitespace(document.page_content)):
            source_chunks.append(Document(page_content=chunk, metadata=document.metadata))

    logging.info(f"Chunked into {len(source_chunks)} documents")
    return source_chunks  

def data_to_embed_pubsub(data: dict, vector_name:str="documents"):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         data JSON
    """
    #hash = data['message']['data']
    message_data = base64.b64decode(data['message']['data']).decode('utf-8')
    attributes = data['message'].get('attributes', {})
    messageId = data['message'].get('messageId')
    publishTime = data['message'].get('publishTime')

    logging.info(f"data_to_embed_pubsub was triggered by messageId {messageId} published at {publishTime}")
    logging.debug(f"data_to_embed_pubsub data: {message_data}")

    # pubsub from a Google Cloud Storage push topic
    if attributes.get("eventType", None) is not None and attributes.get("payloadFormat", None) is not None:
        eventType = attributes.get("eventType")
        payloadFormat = attributes.get("payloadFormat")
        if eventType == "OBJECT_FINALIZE" and payloadFormat == "JSON_API_V1":
            objectId = attributes.get("objectId")
            logging.info(f"Got valid event from Google Cloud Storage: {objectId}")

            if objectId.startswith("config"):
                logging.info(f"Ignoring config file")
                return None
            
            # https://cloud.google.com/storage/docs/json_api/v1/objects#resource-representations
            message_data = 'gs://' + attributes.get("bucketId") + '/' + objectId

            if '/' in objectId:
                bucket_vector_name = objectId.split('/')[0]

                if len(bucket_vector_name) > 0 and vector_name != bucket_vector_name:
                    logging.info(f"Overwriting vector_name {vector_name} with {bucket_vector_name}")
                    vector_name = bucket_vector_name

            attributes["attrs"] = f"namespace:{vector_name}"
            logging.info(f"Constructed message_data: {message_data}")
    
    metadata = attributes

    logging.debug(f"Found metadata in pubsub: {metadata}")

    chunks = []

    if message_data.startswith("gs://"):
        logging.info("Detected gs://")
        bucket_name, file_name = message_data[5:].split("/", 1)

        # Create a client
        storage_client = storage.Client()

        # Download the file from GCS
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(file_name)

        file_name=pathlib.Path(file_name)

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_file_path = os.path.join(temp_dir, file_name.name)
            blob.download_to_filename(tmp_file_path)

            if file_name.suffix == ".pdf":
                pages = split_pdf_to_pages(tmp_file_path, temp_dir)
                if len(pages) > 1: # we send it back to GCS to parrallise the imports
                    logging.info(f"Got back {len(pages)} pages for file {tmp_file_path}")
                    for pp in pages:
                        gs_file = add_file_to_gcs(pp, vector_name=vector_name, bucket_name=bucket_name, metadata=metadata)
                        logging.info(f"{gs_file} is now in bucket {bucket_name}")
                    logging.info(f"Sent split pages for {file_name.name} back to GCS to parrallise the imports")
                    return None
            else:
                # just original temp file
                pages = [tmp_file_path]

            the_metadata = {
                "source": message_data,
                "type": "file_load_gcs",
                "bucket_name": bucket_name
            }
            metadata.update(the_metadata)

            docs = []
            for page in pages:
                logging.info(f"Sending file {page} to loaders.read_file_to_document {metadata}")
                docs2 = loaders.read_file_to_document(page, metadata=metadata, big=True)
                docs.extend(docs2)

            chunks = chunk_doc_to_docs(docs, file_name.suffix)

    elif message_data.startswith("https://drive.google.com") or message_data.startswith("https://docs.google.com"):
        logging.info("Got google drive URL")
        urls = extract_urls(message_data)

        docs = []
        for url in urls:
            metadata["source"] = url
            metadata["url"] = url
            metadata["type"] = "url_load"
            doc = loaders.read_gdrive_to_document(url, metadata=metadata)
            if doc is None:
                logging.info("Could not load any Google Drive docs")
            else:
                docs.extend(doc)

        chunks = chunk_doc_to_docs(docs)
    
    #TODO: support more git service URLs
    elif message_data.startswith("https://github.com"):
        logging.info("Got GitHub URL")
        urls = extract_urls(message_data)

        branch="main"
        if "branch:" in message_data:
            match = re.search(r'branch:(\w+)', message_data)
            if match:
                branch = match.group(1)
        
        logging.info(f"Using branch: {branch}")

        docs = []
        for url in urls:
            metadata["source"] = url
            metadata["url"] = url
            metadata["type"] = "url_load"
            doc = loaders.read_git_repo(url, branch=branch, metadata=metadata)
            if doc is None:
                logging.info("Could not load GitHub files")
            else:
                docs.extend(doc)

        chunks = chunk_doc_to_docs(docs)
        
    elif message_data.startswith("http"):
        logging.info(f"Got http message: {message_data}")

        # just in case, extract the URL again
        urls = extract_urls(message_data)

        docs = []
        for url in urls:
            metadata["source"] = url
            metadata["url"] = url
            metadata["type"] = "url_load"
            doc = loaders.read_url_to_document(url, metadata=metadata)
            docs.extend(doc)

        chunks = chunk_doc_to_docs(docs)

    else:
        logging.info("No gs:// detected")
        
        the_json = json.loads(message_data)
        the_metadata = the_json.get("metadata", {})
        metadata.update(the_metadata)
        the_content = the_json.get("page_content", None)

        if metadata.get("source", None) is not None:
            metadata["source"] = "No source embedded"

        if the_content is None:
            logging.info("No content found")
            return {"metadata": "No content found"}
        
        docs = [Document(page_content=the_content, metadata=metadata)]

        publish_if_urls(the_content, vector_name)

        chunks = chunk_doc_to_docs(docs)

    process_docs_chunks_vector_name(chunks, vector_name, metadata)

    # summarisation of large docs, send them in too
    from qna.summarise import summarise_docs
    summaries = [Document(page_content="No summary made", metadata=metadata)]
    do_summary = False #TODO: use metadata to determine a summary should be made
    if docs is not None and do_summary:
        summaries = summarise_docs(docs, vector_name=vector_name)
        summary_chunks = chunk_doc_to_docs(summaries)
        publish_chunks(summary_chunks, vector_name=vector_name)

        pubsub_manager = PubSubManager(vector_name, pubsub_topic=f"pubsub_state_messages")    
        pubsub_manager.publish_message(
            f"Sent doc chunks with metadata: {metadata} to {vector_name} embedding with summaries:\n{summaries}")

    return metadata


def process_docs_chunks_vector_name(chunks, vector_name, metadata):

    pubsub_manager = PubSubManager(vector_name, pubsub_topic=f"pubsub_state_messages")
    if chunks is None:
        logging.info("No chunks found")
        pubsub_manager.publish_message(f"No chunks for: {metadata} to {vector_name} embedding")
        return None
        
    publish_chunks(chunks, vector_name=vector_name)

    msg = f"data_to_embed_pubsub published chunks with metadata: {metadata}"

    logging.info(msg)
    
    pubsub_manager.publish_message(f"Sent doc chunks with metadata: {metadata} to {vector_name} embedding")

    return metadata    

def publish_if_urls(the_content, vector_name):
    """
    Extracts URLs and puts them in a queue for processing on PubSub
    """
    if contains_url(the_content):
        logging.info("Detected http://")

        urls = extract_urls(the_content)
            
        for url in urls:
            publish_text(url, vector_name)


def publish_chunks(chunks: list[Document], vector_name: str):
    logging.info("Publishing chunks to embed_chunk")
    
    pubsub_manager = PubSubManager(vector_name, pubsub_topic=f"embed_chunk_{vector_name}")
    
    sub_name = f"pubsub_chunk_to_store_{vector_name}"

    sub_exists = pubsub_manager.subscription_exists(sub_name)
    
    if not sub_exists:
        pubsub_manager.create_subscription(sub_name,
                                           push_endpoint=f"/pubsub_chunk_to_store/{vector_name}")
        
    for chunk in chunks:
        # Convert chunk to string, as Pub/Sub messages must be strings or bytes
        chunk_str = chunk.json()
        pubsub_manager.publish_message(chunk_str)
    

def publish_text(text:str, vector_name: str):
    logging.info(f"Publishing text: {text} to app_to_pubsub_{vector_name}")
    pubsub_manager = PubSubManager(vector_name, pubsub_topic=f"app_to_pubsub_{vector_name}")
    sub_name = f"pubsub_to_store_{vector_name}"

    sub_exists = pubsub_manager.subscription_exists(sub_name)
    
    if not sub_exists:
        pubsub_manager.create_subscription(sub_name,
                                           push_endpoint=f"/pubsub_to_store/{vector_name}")
    
    pubsub_manager.publish_message(text)
