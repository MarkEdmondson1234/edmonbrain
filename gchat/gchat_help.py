import re, os, base64, json
import logging
from webapp import bot_help
from qna.pubsub_manager import PubSubManager

def clean_user_input(event):
    bot_name = get_gchat_bot_name_from_event(event)
    user_input = event['message']['text']  # Extract user input from the payload
    user_input = user_input.replace(f'@{bot_name}','').strip()

    return user_input


def send_to_pubsub(the_data, vector_name):
    logging.info(f"Publishing data: {the_data} to app_to_pubsub_{vector_name}")
    pubsub_manager = PubSubManager(vector_name, pubsub_topic=f"gchat_to_pubsub_{vector_name}")
    sub_name = f"pubsub_to_gchat_{vector_name}"

    sub_exists = pubsub_manager.subscription_exists(sub_name)

    if not sub_exists:
        this_url =f"{os.getenv('GCHAT_URL')}/pubsub/callback"

        pubsub_manager.create_subscription(sub_name,
                                           push_endpoint=this_url)
        
    the_data['vector_name'] = vector_name

    pubsub_manager.publish_message(the_data)

    return True

def process_pubsub_data(data):
    event = base64.b64decode(data['message']['data']).decode('utf-8')

    logging.info(f'process_pubsub_data for gchat got event: {event} {type(event)}')

    event = json.loads(event)

    user_input = clean_user_input(event)
    vector_name = event['vector_name']

    # Get the spaceId from the event
    space_id = event['space']['name']

    if event['message'].get('slashCommand', None) is not None:
        response = handle_slash_commands(event['message']['slashCommand'])
        if response is not None:
            logging.info(f'Changing to vector_name: {vector_name} in response to slash_command')
            vector_name = response
            user_input = remove_slash_command(user_input)

    chat_history = list_messages(space_id)

    command_response = bot_help.handle_special_commands(user_input, vector_name, chat_history)
    if command_response is not None:
        bot_output = command_response
    else:
        paired_history = bot_help.extract_chat_history(chat_history)
        logging.info(f"Asking for reply for: {user_input}")
        bot_output = bot_help.send_to_qa(user_input, vector_name, chat_history=paired_history)
        logging.info(f"Got back reply for: {user_input}")

    return bot_output, vector_name, space_id


def remove_slash_command(text):
    """'/chat blah foo' will become: 'blah foo'"""
    return re.sub(r'^/\w+\b', '', text).strip()

def handle_slash_commands(slashCommand):
    commandId = slashCommand.get('commandId', None)
    logging.info(f'CommandId: {commandId}')
    if commandId is None:
        logging.error('Got a slash_command with no commandId specified')
        return None
    
    COMMAND_LOOKUP = {
        "1": "codey" # used to change vector_name
    }

    if commandId in COMMAND_LOOKUP:
        logging.info(f'COMMAND_LOOKUP[commandId] {COMMAND_LOOKUP[commandId]}')
        return COMMAND_LOOKUP[commandId]
    
    return None

def get_gchat_bot_name_from_event(event):
    """Extract bot name from GChat event.

    Args:
        event (dict): GChat event.

    Returns:
        str: Bot name if found, None otherwise.
    """
    annotations = event['message'].get('annotations', [])
    for annotation in annotations:
        if annotation['type'] == 'USER_MENTION':
            return annotation['userMention']['user']['displayName']
    return None

def generate_google_chat_card(bot_output, how_many = 1):
    source_documents = []
    if bot_output.get('source_documents', None) is not None:
        for doc in bot_output['source_documents']:
            metadata = doc.get("metadata", None)
            page_content = doc.get("page_content", None)
            if metadata is None or page_content is None:
                continue
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
                'header': page_content[:30],
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


from google.auth import exceptions, default
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def send_to_gchat(gchat_output, space_id):
    try:
        creds, _ = default()
        chat = build('chat', 'v1', credentials=creds)
        message = chat.spaces().messages().create(
            parent=space_id,
            body=gchat_output
        ).execute()
        print('Message sent: %s' % message)
    except exceptions.DefaultCredentialsError as e:
        print('Error in creating credentials: %s' % e)
    except Exception as e:
        print('Error in sending message: %s' % e)

def list_messages(space_id):
    creds, _ = default()
    chat = build('chat', 'v1', credentials=creds)
    result = chat.spaces().messages().list(
        parent = space_id,
    ).execute()

    if len(result) == 0:
        return None
    
    return result
    
