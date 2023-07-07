import sys, os
# https://github.com/slackapi/bolt-python/blob/main/examples/fastapi/async_app.py
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import logging
import json
from webapp import bot_help
import aiohttp

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
    
    # this breaks it? Its sending it multiple times though
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

    chat_historys = await sapp.client.conversations_replies(
        channel=body['event']['channel'],
        ts=thread_ts
    ) if thread_ts else await sapp.client.conversations_history(
        channel=body['event']['channel']
    )

    messages = chat_historys['messages']

    command_response = bot_help.handle_special_commands(user_input, vector_name, messages)
    if command_response is not None:
        return command_response['result']
    

    logging.info(f'Sending from Slack: {user_input} to {vector_name}')
    bot_output = await send_to_qa_async(user_input, vector_name, chat_history=messages)
    logging.info(f"Slack bot_output: {bot_output}")

    slack_output = bot_output.get("answer", "No answer available")

    return slack_output

def load_config(filename):
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Join the script directory with the filename
    config_path = os.path.join(parent_dir, filename)

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

slack_config = load_config('slack/slack_config.json')

def get_slack_vector_name(team_id, bot_user):
    logging.info(f'getting slack vector_name: {team_id} - {bot_user}')
    try:
        return slack_config['team_ids'][team_id]['bot_users'][bot_user]['llm']
    except KeyError:
        logging.error('Could not find slack config')
        return None