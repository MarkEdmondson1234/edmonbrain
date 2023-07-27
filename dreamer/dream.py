from datetime import datetime
import logging, os
from google.cloud import bigquery
from google.cloud import storage
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate

def fetch_data_from_bigquery(date, vector_name):
    client = bigquery.Client()

    # Read the main SQL query from a file and execute it
    with open('dreamer/query.sql', 'r') as file:
        sql = file.read().replace('{date}', date).replace('{vector_name}', vector_name)
    
    logging.info('Executing SQL query: {}'.format(sql))
    query_job = client.query(sql)  # This makes an API request.
    rows = list(query_job.result())  # Waits for the query to finish.

    if len(rows) < 10:
        # Read the additional SQL query from a file and execute it
        with open('dreamer/query_random.sql', 'r') as file:
            sql_random = file.read() \
                            .replace('{date}', date) \
                            .replace('{limit}', str(10-len(rows))) \
                            .replace('{vector_name}', vector_name)
        
        logging.info('Executing random SQL query: {}'.format(sql))
        query_job = client.query(sql_random)
        rows_random = list(query_job.result())
        rows.extend(rows_random)

    return rows


def prepare_llm_input(rows):
    llm_input = "Todays events:\n\n"
    for row in rows:
        if row['question']:
            llm_input += f"**Question:** {row['question']}\n\n"
        if row['bot_output']:
            llm_input += f"**Bot Output:** {row['bot_output']}\n\n"
        if row['chat_history']:
            llm_input += f"**Chat History:** {row['chat_history']}\n\n"
        if row['source_documents_page_contents']:
            llm_input += "**Source Documents Page Contents:**\n\n"
            for page_content in row['source_documents_page_contents']:
                llm_input += f"- {page_content}\n\n"
    # 13k max string length
    return llm_input[:13000]


def cheap_summary(docs):
    # make a summary first to avoid gpt-4 rate limits
    llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0, max_tokens=3048)
    prompt_template = """Summarise the events below including sections for questions, answers, chat history and source documents

{text}

YOUR SUMMARY:
Questions:
Bot outputs:
Chat history:
Source documents:"""
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])
    chain1 = load_summarize_chain(llm, chain_type="stuff", verbose=True, prompt=PROMPT)
    summary = chain1.run(docs)

    # Create documents
    return summary

def summarise_conversations(docs, temperature=0.9, type="dream"):
    if type=="dream":
        prompt_template = """Use the following events from today to create a dream. 
Reflect on the unique events that happened today, and speculate a lot on what they meant, both what led to them and what those events may mean for the future. 
Practice future scenarios that may use the experiences you had today. 
Assess the emotional underpinnings of the events. Use symbolism within the dream to display the emotions and major themes involved.

{text}

YOUR DREAM TRANSCRIPT:"""
        PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])

        llm_dream = ChatOpenAI(model="gpt-4", temperature=temperature, max_tokens=3600)
        chain2 = load_summarize_chain(llm_dream, chain_type="stuff", verbose=True, prompt=PROMPT)
        summary = chain2.run(docs)
        
    elif type=="journal":
        summary = cheap_summary(docs)
    elif type=="practice":
        prompt_template = """Consider the events below, and role play possible likely future scenarios that would draw upon thier information.
Don't repeat the same questions and answers, do similar but different.
Role play a human and yourself as an AI answering questions the human would be interested in.
Suggest interesting questions to the human that may be interesting, novel or can be useful to achieve the tasks.

{text}

YOUR ROLE PLAY:
Human:
AI:
"""
        PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])

        llm_dream = ChatOpenAI(model="gpt-4", temperature=temperature, max_tokens=3600)
        chain2 = load_summarize_chain(llm_dream, chain_type="stuff", verbose=True, prompt=PROMPT)
        summary = chain2.run(docs)

    else:
        raise ValueError("You must set a type of 'practice', 'journal' or 'dream'")
    
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
    import time
    # Get today's date
    today_date = datetime.today().strftime('%Y-%m-%d')

    # Fetch today's conversations data from BigQuery
    rows = fetch_data_from_bigquery(today_date, vector_name=vector_name)

    # Prepare LLM input
    llm_input = prepare_llm_input(rows)

    # Split text
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024)
    texts = text_splitter.split_text(llm_input)

    # Create documents
    docs = [Document(page_content=t) for t in texts]

    journal = summarise_conversations(docs, temperature=0, type="journal")
    docs2 = [Document(page_content=journal)]
    # Summarize the conversations
    dream = summarise_conversations(docs2, temperature=0.9, type="dream")
    practice = summarise_conversations(docs2, temperature=0.6, type="practice")

    # Upload to input into brain
    dream_blob_name = f'{vector_name}/dreams/dream_{today_date}.txt'
    journal_blob_name = f'{vector_name}/journal/journal_{today_date}.txt'
    practice_blob_name = f'{vector_name}/practice/practice_{today_date}.txt'

    upload_blob(dream, dream_blob_name)
    upload_blob(journal, journal_blob_name)
    upload_blob(practice, practice_blob_name)

if __name__ == "__main__":
    dream('edmonbrain')
