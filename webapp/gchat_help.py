import re
import logging

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