import os
import re
import logging
import base64
import json
import datetime
import requests
import tempfile

import qna.database as db
import chunker.publish_to_pubsub_embed as pbembed
from google.cloud import storage


def generate_webapp_output(bot_output):
    source_documents = []
    if bot_output.get('source_documents', None) is not None:
        source_documents = []
        for doc in bot_output['source_documents']:
            metadata = doc.get("metadata",{})
            filtered_metadata = {}
            if metadata.get("source", None) is not None:
                filtered_metadata["source"] = metadata["source"]
            if metadata.get("type", None) is not None:
                filtered_metadata["type"] = metadata["type"]
            source_doc = {
                'page_content': doc["page_content"],
                'metadata': filtered_metadata
            }
            source_documents.append(source_doc)

    return {
        'result': bot_output.get('answer', "No answer available"),
        'source_documents': source_documents
    }

def discord_webhook(message_data):
    webhook_url = os.getenv('DISCORD_URL', None)  # replace with your webhook url
    if webhook_url is None:
        return None
    
    logging.info(f'webhook url: {webhook_url}')

    # If the message_data is not a dict, wrap it in a dict.
    if not isinstance(message_data, dict):
        message_data = {'content': message_data}
    else:
        # if it is a dict, turn it into a string
        message_data = {'content': json.dumps(message_data)}
        #TODO parse out message_data into other discord webhook objects like embed
        # https://birdie0.github.io/discord-webhooks-guide/discord_webhook.html
    
    data = message_data

    logging.info(f'Sending discord this data: {data}')
    response = requests.post(webhook_url, json=data,
                            headers={'Content-Type': 'application/json'})
    logging.debug(f'Sent data to discord: {response}')
    
    return response

def process_pubsub(data):

    logging.debug(f'process_pubsub: {data}')
    message_data = base64.b64decode(data['message']['data']).decode('utf-8')
    messageId = data['message'].get('messageId')
    publishTime = data['message'].get('publishTime')

    logging.debug(f"This Function was triggered by messageId {messageId} published at {publishTime}")
    # DANGER: Will trigger this dunction recursivly
    #logging.info(f"bot_help.process_pubsub message data: {message_data}")

    try:
        message_data = json.loads(message_data)
    except:
        logging.debug("Its not a json")

    if message_data:
        return message_data
    
    logging.info(f"message_data was empty")
    return ''

def app_to_store(safe_file_name, vector_name, via_bucket_pubsub=False, metadata:dict=None):
    
    gs_file = pbembed.add_file_to_gcs(safe_file_name, vector_name, metadata=metadata)

    # we send the gs:// to the pubsub ourselves
    if not via_bucket_pubsub:
        pbembed.publish_text(gs_file, vector_name)

    return gs_file
    
def handle_files(uploaded_files, temp_dir, vector_name):
    bot_output = []
    if uploaded_files:
        for file in uploaded_files:
            # Save the file temporarily
            safe_filepath = os.path.join(temp_dir, file.filename)
            file.save(safe_filepath)

            app_to_store(safe_filepath, vector_name)
            bot_output.append(f"{file.filename} sent to {vector_name}")

    return bot_output

def generate_discord_output(bot_output):
    source_documents = []
    if bot_output.get('source_documents', None) is not None:
        source_documents = []
        for doc in bot_output['source_documents']:
            metadata = doc.get("metadata",{})
            filtered_metadata = {}
            if metadata.get("source", None) is not None:
                filtered_metadata["source"] = metadata["source"]
            if metadata.get("type", None) is not None:
                filtered_metadata["type"] = metadata["type"]
            source_doc = {
                'page_content': doc["page_content"],
                'metadata': filtered_metadata
            }
            source_documents.append(source_doc)

    return {
        'result': bot_output.get('answer', "No answer available"),
        'source_documents': source_documents
    }

def embeds_to_json(message):
    return json.dumps(message.get("embeds")) if message.get("embeds", None) else None

def create_message_element(message):
    if 'text' in message:  # This is a Slack or Google Chat message
        return message['text']
    else:  # This is a message in Discord format
        return message["content"] + ' Embeds: ' + embeds_to_json(message) if embeds_to_json(message) else ''

def is_human(message):
    if 'name' in message:
        return message["name"] == "Human"
    elif 'sender' in message:  # Google Chat
        return message['sender']['type'] == 'HUMAN'
    else:
        return 'user' in message  # Slack

def is_ai(message):
    if 'name' in message:
        return message["name"] == "AI"
    elif 'sender' in message:  # Google Chat
        return message['sender']['type'] == 'BOT'
    else:
        return 'bot_id' in message  # Slack


def extract_chat_history(chat_history=None):
    
    if chat_history:
        # Separate the messages into human and AI messages
        human_messages = [create_message_element(message) for message in chat_history if is_human(message)]
        ai_messages = [create_message_element(message) for message in chat_history if is_ai(message)]
        # Pair up the human and AI messages into tuples
        paired_messages = list(zip(human_messages, ai_messages))
    else:
        print("No chat history found")
        paired_messages = []

    return paired_messages

def handle_special_commands(user_input, vector_name, chat_history):
    now = datetime.datetime.now()
    hourmin = now.strftime("%H%M%S")
    the_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    chat_history = extract_chat_history(chat_history)
    if user_input.startswith("!savethread"):
        with tempfile.TemporaryDirectory() as temp_dir:
            chat_file_path = os.path.join(temp_dir, f"{hourmin}_chat_history.txt")
            with open(chat_file_path, 'w') as file:
                file.write(f"## Thread history at {the_datetime}\nUser: {user_input}")
                for human_message, ai_message in chat_history:
                    file.write(f"Human: {human_message}\nAI: {ai_message}\n")
            gs_file = app_to_store(chat_file_path, vector_name, via_bucket_pubsub=True)
            return {"result": f"Saved chat history to {gs_file}"}

    elif user_input.startswith("!saveurl"):
        if pbembed.contains_url(user_input):
            urls = pbembed.extract_urls(user_input)
            branch="main"
            if "branch:" in user_input:
                match = re.search(r'branch:(\w+)', user_input)
                if match:
                    branch = match.group(1)
            for url in urls:
                pbembed.publish_text(f"{url} branch:{branch}", vector_name)
            return {"result": f"URLs sent for processing: {urls} to {vector_name}."}
        else:
            return {"result": f"No URLs were found"}

    elif user_input.startswith("!deletesource"):
        source = user_input.replace("!deletesource", "")
        source = source.replace("source:","").strip()
        db.delete_row_from_source(source, vector_name=vector_name)
        return {"result": f"Deleting source: {source}"}

    elif user_input.startswith("!sources"):
        rows = db.return_sources_last24(vector_name)
        if rows is None:
            return {"result": "No sources were found"}
        else:
            msg = "\n".join([f"{row}" for row in rows])
            return {"result": f"*sources:*\n{msg}"}


    elif user_input.startswith("!help"):
        return {"result":f"""*Commands*
- `!saveurl [https:// url]` - add the contents found at this URL to database. 
- `!help`- see this message
- `!sources` - get sources added in last 24hrs
- `!deletesource [gs:// source]` - delete a source from database
- `!dream` - get last night's dream. Use `!dream 2023-07-30` to get a dream from a specific date. Also works with `!journal` and `!practice`
*Tips*
- See user guide here: https://docs.google.com/document/d/1WMi5X4FVHCihIkZ69gzxkVzr86m4WQj3H75LjSPjOtQ
- Attach files to Discord messages to upload them into database
- If you have access, upload big files (>5MB) to the Google Cloud Storage bucket
- URLs of GoogleDrive work only if shared with **edmonbrain-app@devo-mark-sandbox.iam.gserviceaccount.com** in your own drive
- URLs of GitHub (https://github.com/* branch:main) will git clone and add all repo files. e.g. `!saveurl https://github.com/me/repo branch:master`. 
- For private GitHub repositories, the app has a GitHub PAT that will need access linked to MarkEdmondson1234 account
*Slash Commands*
"""}
    
    # check for special text file request via !dream !journal or !practice
    result = get_gcs_text_file(user_input, vector_name)
    if result:
        return {"result": result}

    # If no special commands were found, return None
    return None

def get_gcs_text_file(user_input, vector_name):
    command = None
    for keyword in ["!dream", "!journal", "!practice"]:
        if user_input.startswith(keyword):
            command = keyword.strip('!')
            break

    if not command:
        return None

    dream_date = datetime.datetime.now() - datetime.timedelta(1)
    if ' ' in user_input:
        _, date_str = user_input.split(' ', 1)
        try:
            dream_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return f"Invalid date format for !{command}. Use YYYY-MM-DD."

    dream_date_str = dream_date.strftime('%Y-%m-%d')

    bucket_name = os.getenv("GCS_BUCKET").replace("gs://","") 
    source_blob_name = f"{vector_name}/{command}/{command}_{dream_date_str}.txt"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(source_blob_name)
    if blob.exists():
        dream_text = blob.download_as_text()
        return dream_text
    else:
        return f"!{command} file does not exist for date {dream_date_str}"




def load_config(filename):
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Join the script directory with the filename
    config_path = os.path.join(parent_dir, filename)

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def send_to_qa(user_input, vector_name, chat_history, message_author=None):

    qna_url = os.getenv('QNA_URL', None)
    if qna_url is None:
       raise ValueError('QNA_URL not found in environment')

    qna_endpoint = f'{qna_url}/qna/{vector_name}'
    qna_data = {
        'user_input': user_input,
        'chat_history': chat_history,
        'message_author': message_author
    }
    try:
        logging.info(f"Sending to {qna_endpoint} this data: {qna_data}")
        qna_response = requests.post(qna_endpoint, json=qna_data)
        qna_response.raise_for_status()  # Raises a HTTPError if the response status is 4xx, 5xx
    except requests.exceptions.HTTPError as err:
        logging.error(f"HTTP error occurred: {err}")
        return {"answer": f"There was an error processing your request. Please try again later. {str(err)}"}
    except Exception as err:
        logging.error(f"Other error occurred: {str(err)}")
        return {"answer": f"Something went wrong. Please try again later. {str(err)}"}
    else:
        logging.info(f"Got back QA response: {qna_response}")
        return qna_response.json()

import aiohttp
import asyncio

async def send_to_qa_async(user_input, vector_name, chat_history):

    qna_url = os.getenv('QNA_URL', None)
    if qna_url is None:
       raise ValueError('QNA_URL not found in environment')

    qna_endpoint = f'{qna_url}/qna/{vector_name}'
    qna_data = {
        'user_input': user_input,
        'chat_history': chat_history,
    }
    logging.info(f"Sending to {qna_endpoint} this data: {qna_data}")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(qna_endpoint, json=qna_data) as resp:
            qna_response = await resp.json()

    logging.info(f"Got back QA response: {qna_response}")
    return qna_response
