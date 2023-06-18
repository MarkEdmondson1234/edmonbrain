import os
import logging
import base64
import json
import datetime
import requests
import tempfile

import qna.database as db
import qna.publish_to_pubsub_embed as pbembed

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
    logging.info(f'Sent data to discord: {response}')
    
    return response

def process_pubsub(data):

    logging.info(f'process_pubsub: {data}')
    message_data = base64.b64decode(data['message']['data']).decode('utf-8')
    messageId = data['message'].get('messageId')
    publishTime = data['message'].get('publishTime')

    logging.info(f"This Function was triggered by messageId {messageId} published at {publishTime}")
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
            metadata = doc.metadata
            filtered_metadata = {}
            if metadata.get("source", None) is not None:
                filtered_metadata["source"] = metadata["source"]
            if metadata.get("type", None) is not None:
                filtered_metadata["type"] = metadata["type"]
            source_doc = {
                'page_content': doc.page_content,
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
    if 'text' in message:  # This is a Slack message
        return message['text']
    else:  # This is a message in Discord format
        return message["content"] + ' Embeds: ' + embeds_to_json(message) if embeds_to_json(message) else message["content"]

def is_human(message):
    if 'name' in message:
        return message["name"] == "Human"
    else:
        return 'user' in message # Slack

def is_ai(message):
    if 'name' in message:
        return message["name"] == "AI"
    else:
        return 'bot_id' in message # Slack

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
    hourmin = now.strftime("%H%M")

    if user_input.startswith("!savethread"):
        with tempfile.TemporaryDirectory() as temp_dir:
            chat_file_path = os.path.join(temp_dir, f"{hourmin}_chat_history.txt")
            with open(chat_file_path, 'w') as file:
                for chat in chat_history:
                    file.write(f"{chat['name']}: {chat['content']}\n")
            gs_file = app_to_store(chat_file_path, vector_name, via_bucket_pubsub=True)
            return {"result": f"Saved chat history to {gs_file}"}

    elif user_input.startswith("!saveurl"):
        if pbembed.contains_url(user_input):
            urls = pbembed.extract_urls(user_input)
            for url in urls:
                pbembed.publish_text(url, vector_name)
            return {"result": f"URLs sent for processing: {urls}"}
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
        return {"result":f"""* `!sources` - get sources added in last 24hrs
* `!deletesource [gs:// source]` - delete a source from database
* `!saveurl [https:// url]` - add the contents found at this URL to database. 
* `!savethread` - save current Discord thread as a source to database
* `!help`- see this message
* Files attached to discord messages will be added as source to database
* Add files to the specified Cloud Storage folder to also add them to database
* URLs of GoogleDrive work only if shared with *edmonbrain-app@devo-mark-sandbox.iam.gserviceaccount.com* in your own drive
"""}

    # If no special commands were found, return None
    return None

def generate_google_chat_card(bot_output, how_many = 1):
    source_documents = []
    if bot_output.get('source_documents', None) is not None:
        for doc in bot_output['source_documents']:
            metadata = doc.metadata
            filtered_metadata = {}
            if metadata.get("source", None) is not None:
                filtered_metadata["source"] = metadata["source"]
            if metadata.get("type", None) is not None:
                filtered_metadata["type"] = metadata["type"]
            if metadata.get("title", None) is not None:
                filtered_metadata["title"] = metadata["title"]
            if metadata.get("page", None) is not None:
                filtered_metadata["page"] = metadata["page"]
            if metadata.get("category", None) is not None:
                filtered_metadata["category"] = metadata["category"]
            source_doc = {
                'header': doc.page_content[:30],
                'metadata': filtered_metadata
            }
            source_documents.append(source_doc)

    card = {
        'cards': [
            {
                'header': {
                    'title': 'Edmonbrain output'
                },
                'sections': [
                    {
                    'header': 'Answer',
                    'widgets':[
                            {
                                'textParagraph': {
                                    'text': bot_output.get('answer', "No answer available")
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    i = 0
    for source_doc in source_documents:
        i += 1
        card['cards'][0]['sections'].append({
            'header': 'Source',
            'widgets': [
                {
                    'textParagraph': {
                        'text': source_doc['metadata'].get('source', '')
                    }
                },
                {
                    'textParagraph': {
                        'text': source_doc['metadata'].get('type', '') + \
                            ' ' + source_doc['metadata'].get('title', '') + \
                            ' ' + source_doc['metadata'].get('category', '') + \
                            ' ' + source_doc['metadata'].get('page', '')
                    }
                }
            ]
        })
        if i == how_many:
            break

    return card

def handle_slash_commands(slash_command):
    commandId = slash_command.get('commandId', None)
    if commandId is None:
        logging.error('Got a slash_command with no commandId specified')
        return None
    
    COMMAND_LOOKUP = {
        "1": "codey" # used to change vector_name
    }

    if commandId in COMMAND_LOOKUP:
        return COMMAND_LOOKUP[commandId]
    
    return None

def load_config(filename):
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Join the script directory with the filename
    config_path = os.path.join(parent_dir, filename)

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config