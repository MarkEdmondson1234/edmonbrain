import sys, os
import traceback
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

# app.py
from flask import Flask, request, jsonify, Response
import qna.question_service as qs
from qna.archive import archive_qa

import logging


app = Flask(__name__)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

from google.cloud import storage

app = Flask(__name__)

# Initialize Google Cloud Storage client
storage_client = storage.Client()

# The name of your bucket and the file you want to check
bucket_name = os.environ.get('GCS_BUCKET')
if bucket_name:
    bucket_name = bucket_name.replace('gs://', '')
else:
    raise EnvironmentError("GCS_BUCKET environment variable not set")

blob_name = 'local_config.json'

# Global variable to store the last modification time
last_mod_time = None


def fetch_config():
    global last_mod_time

    bucket = storage_client.bucket(bucket_name)
    blob = storage.Blob(blob_name, bucket)

    # Check if the file exists
    if not blob.exists():
        logging.info(f"The blob {blob_name} does not exist in the bucket {bucket_name}")
        return None

    # Download the file to a local file
    blob.download_to_filename('config.com')

    # Get the blob's updated time
    updated_time = blob.updated

    return updated_time


@app.before_request
def before_request():
    global last_mod_time
    
    # Fetch the current modification time from Cloud Storage
    current_mod_time = fetch_config()
    
    if current_mod_time:
        # Compare the modification times
        if last_mod_time is None or last_mod_time < current_mod_time:
            last_mod_time = current_mod_time
            logging.info("Configuration file updated, reloaded the new configuration.")
        else:
            logging.info("Configuration file not modified.")

def document_to_dict(document):
    return {
        "page_content": document.page_content,
        "metadata": document.metadata
    }

def parse_output(bot_output):
    if 'source_documents' in bot_output:
        bot_output['source_documents'] = [document_to_dict(doc) for doc in bot_output['source_documents']]
    if bot_output.get("answer", None) is None or bot_output.get("answer") == "":
        bot_output['answer'] = "(No text was returned)"
    return bot_output

def create_message_element(message):
    if 'text' in message:  # This is a Slack message
        return message['text']
    else:  # This is a message in Discord format
        return message["content"]

def is_human(message):
    if 'name' in message:
        return message["name"] == "Human"
    elif 'sender' in message:  # Google Chat
        return message['sender']['type'] == 'HUMAN'
    else:
        # Slack: Check for the 'user' field and absence of 'bot_id' field
        return 'user' in message and 'bot_id' not in message

def is_bot(message):
    return not is_human(message)

def extract_chat_history(chat_history=None):

    if chat_history:
        logging.info(f"Extracting chat history: {chat_history}")
        paired_messages = []

        first_message = chat_history[0]
        if is_bot(first_message):
            blank_human_message = {"name": "Human", "content": "", "embeds": []}
            paired_messages.append((create_message_element(blank_human_message), 
                                    create_message_element(first_message)))
            chat_history = chat_history[1:]

        last_human_message = ""
        for message in chat_history:
            if is_human(message):
                last_human_message = create_message_element(message)
            elif is_bot(message):
                ai_message = create_message_element(message)
                paired_messages.append((last_human_message, ai_message))
                last_human_message = ""

    else:
        logging.info("No chat history found")
        paired_messages = []

    logging.info(f"Paired messages: {paired_messages}")

    return paired_messages

@app.route('/qna/discord/streaming/<vector_name>', methods=['POST'])
def stream_qa(vector_name):
    data = request.get_json()
    logging.info(f"qna/discord/streaming/{vector_name} got data: {data}")

    user_input = data['content'].strip()  # Extract user input from the payload

    chat_history = data.get('chat_history', None)

    message_author = data.get('message_author', None)

    from webapp import bot_help
    paired_messages = bot_help.extract_chat_history(chat_history)

    command_response = bot_help.handle_special_commands(user_input, vector_name, paired_messages)
    if command_response is not None:
        return jsonify(command_response)

    paired_messages = extract_chat_history(data['chat_history'])
    logging.info(f'Stream QNA got: {user_input}')
    logging.info(f'Stream QNA got chat_history: {paired_messages}')

    from qna.streaming import start_streaming_chat
    response = Response(start_streaming_chat(user_input,
                                             vector_name,
                                             chat_history=paired_messages,
                                             message_author=message_author), 
                        content_type='text/plain')
    response.headers['Transfer-Encoding'] = 'chunked'    

    return response

@app.route('/qna/<vector_name>', methods=['POST'])
def process_qna(vector_name):
    data = request.get_json()
    logging.info(f"qna/{vector_name} got data: {data}")

    user_input = data['user_input']

    message_author = data.get('message_author', None)

    paired_messages = extract_chat_history(data['chat_history'])
    logging.info(f'QNA got: {user_input}')
    logging.info(f'QNA got chat_history: {paired_messages}')
    try:
        bot_output = qs.qna(user_input, vector_name, chat_history=paired_messages, message_author=message_author)
        bot_output = parse_output(bot_output)
        archive_qa(bot_output, vector_name)
    except Exception as err: 
        bot_output = {'answer': f'QNA_ERROR: An error occurred while processing /qna/{vector_name}: {str(err)} traceback: {traceback.format_exc()}'}
    logging.info(f'==LLM Q:{user_input} - A:{bot_output["answer"]}')
    return jsonify(bot_output)

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

