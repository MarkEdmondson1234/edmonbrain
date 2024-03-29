import sys, os
# https://github.com/slackapi/bolt-python/blob/main/examples/fastapi/async_app.py
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import logging
import json
from webapp import bot_help
import aiohttp
from utils.config import load_config

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

async def process_slack_message(sapp, body, logger, thread_ts=None):
    logger.info(body)
    logging.info("Calling async process_slack_message")
    team_id = body.get('team_id', None)
    if team_id is None:
        raise ValueError('Team_id not specified')
    user_input = body.get('event').get('text','').strip()

    user = body.get('event').get('user')
    bot_user = body.get('authorizations')[0].get('user_id')

    bot_mention = f"<@{bot_user}>"
    user_input = user_input.replace(bot_mention, '').strip()

    vector_name = get_slack_vector_name(team_id, bot_user)
    if vector_name is None:
        raise ValueError(f'Could not derive vector_name from slack_config and {team_id}, {bot_user}')
    
    logging.debug(f'Slack vector_name: {vector_name}')
    logging.info(f"Getting Slack histories from {body['event']['channel']}")

    logging.info(f"thread_ts: {thread_ts}")

    if not thread_ts:
        logging.info(f"Getting Slack history sapp.client.conversations_history")
        chat_historys = await sapp.client.conversations_history(channel=body['event']['channel'], limit=50)
    else:
        logging.info(f"Getting Slack history sapp.client.conversations_replies")
        chat_historys = await sapp.client.conversations_replies(
            channel=body['event']['channel'],
            ts=thread_ts)
        if len(chat_historys['messages']) == 1:
            logging.warning("using converstaions_history instead")
            chat_historys = await sapp.client.conversations_history(channel=body['event']['channel'], limit=50)

    logging.debug(f'Slack historys obj: {chat_historys}')

    messages = chat_historys['messages']
    logging.info(f'Slack history found: {len(messages)} messages using thread_ts: {thread_ts}')

    command_response = bot_help.handle_special_commands(user_input, vector_name, messages)
    if command_response is not None:
        bot_output = {}
        bot_output["answer"] = command_response["result"]
    else:
        logging.info(f'Sending from Slack: {user_input} to {vector_name}')
        bot_output = await send_to_qa_async(user_input, vector_name, chat_history=messages)
    
    logging.info(f"Slack bot_output: {bot_output}")

    return generate_slack_output(bot_output)

def generate_slack_output(bot_output):
    answer_text = bot_output.get("answer", "No answer available")
    truncation_msg = "..(slack character limit reached (3000))"
        
    # If the answer_text length exceeds the slack limit after appending the truncation message
    if len(answer_text) > (3000 - len(truncation_msg)):
        answer_text = answer_text[:2956] + truncation_msg
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": answer_text}
        }
    ]

    if bot_output.get("source_documents", None) is not None:
        logging.info(f'Found source documents: {bot_output.get("source_documents")}')
        for docss in bot_output["source_documents"]:
            doc_source = docss.get("metadata", None).get("source", None)
            if doc_source is not None:
                source_block = {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*source*: `{doc_source}`"
                        }
                    ]
                }
                blocks.append(source_block)

    return blocks

def get_slack_vector_name(team_id, bot_user):
    slack_config = load_config('slack/slack_config.json')
    logging.info(f'getting slack vector_name: {team_id} - {bot_user}')
    try:
        return slack_config['team_ids'][team_id]['bot_users'][bot_user]['llm']
    except KeyError:
        logging.error('Could not find slack config')
        return None