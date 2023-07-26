from datetime import datetime
import logging, os
from google.cloud import bigquery
from google.cloud import storage
from langchain.docstore.document import Document
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate

def fetch_data_from_bigquery(date):
    client = bigquery.Client()

    # Read the main SQL query from a file and execute it
    with open('dreamer/query.sql', 'r') as file:
        sql = file.read().replace('{date}', date)
    
    logging.info('Executing SQL query: {}'.format(sql))
    query_job = client.query(sql)  # This makes an API request.
    rows = list(query_job.result())  # Waits for the query to finish.

    if len(rows) < 10:
        # Read the additional SQL query from a file and execute it
        with open('dreamer/query_random.sql', 'r') as file:
            sql_random = file.read().replace('{date}', date).replace('{limit}', str(10-len(rows)))
        
        logging.info('Executing random SQL query: {}'.format(sql))
        query_job = client.query(sql_random)
        rows_random = list(query_job.result())
        rows.extend(rows_random)

    return rows


def prepare_llm_input(rows):
    llm_input = "Todays events:\n\n"
    for row in rows:
        llm_input += f"**Question:** {row['question']}\n\n"
        llm_input += f"**Bot Output:** {row['bot_output']}\n\n"
        llm_input += f"**Chat History:** {row['chat_history']}\n\n"
        llm_input += "**Source Documents Page Contents:**\n\n"
        for page_content in row['source_documents_page_contents']:
            llm_input += f"- {page_content}\n\n"
    return llm_input

def summarise_conversations(docs):
    llm = ChatOpenAI(model="gpt-4", temperature=0.9, max_tokens=5000)
    prompt_template = """Use the following events from today to create a dream. 
Reflect on the unique events that happened today, and speculate a lot on what they meant, both what led to them and what those events may mean for the future. 
Practice future scenarios that may use the experiences you had today. 
Assess the emotional underpinnings of the events. Use symbolism within the dream to display the emotions and major themes involved.

{text}

YOUR DREAM TRANSCRIPT:"""
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])

    chain = load_summarize_chain(llm, chain_type="stuff", prompt=PROMPT)
    summary = chain.run(docs)

    return summary

def upload_blob(content, destination_blob_name):
    bucket_name = os.getenv('GCS_BUCKET', None)
    bucket_name = bucket_name.replace('gs://','')
    if bucket_name is None:
        raise ValueError("No bucket found to upload to: GCS_BUCKET returned None")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_string(content)

    logging.info(
        "File {} uploaded to {}.".format(
            destination_blob_name, bucket_name
        )
    )


def dream(vector_name):
    # Get today's date
    today_date = datetime.today().strftime('%Y-%m-%d')

    # Fetch today's conversations data from BigQuery
    rows = fetch_data_from_bigquery(today_date)

    # Prepare LLM input
    llm_input = prepare_llm_input(rows)

    # Split text
    text_splitter = CharacterTextSplitter()
    texts = text_splitter.split_text(llm_input)

    # Create documents
    docs = [Document(page_content=t) for t in texts]

    # Summarize the conversations
    summary = summarise_conversations(docs)

    # Define the destination blob name
    destination_blob_name = f'{vector_name}/dreams/dream_{today_date}.txt'

    # Upload content to the bucket
    upload_blob(summary, destination_blob_name)

if __name__ == "__main__":
    dream('edmonbrain')
