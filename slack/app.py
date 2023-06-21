import sys, os
# https://github.com/slackapi/bolt-python/blob/main/examples/fastapi/async_app.py
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import uvicorn
from fastapi import FastAPI, Request
import logging
from webapp import bot_help
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
import aiohttp
import asyncio

app = AsyncApp()
app_handler = AsyncSlackRequestHandler(app)

api = FastAPI()

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
    user_input = body.get('event').get('text').strip()

    

    user = body.get('event').get('user')
    bot_user = body.get('authorizations')[0].get('user_id')

    bot_mention = f"<@{bot_user}>"
    user_input = user_input.replace(bot_mention, "").strip()

    vector_name = bot_help.get_slack_vector_name(team_id, bot_user)
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
    
    return user_input + vector_name

    logging.info(f'Sending from Slack: {user_input} to {vector_name}')
    bot_output = await send_to_qa_async(user_input, vector_name, chat_history=messages)
    logging.info(f"Slack bot_output: {bot_output}")

    slack_output = bot_output.get("answer", "No answer available")

    return slack_output

@app.event("app_mention")
async def handle_app_mention(ack, body, say, logger):
    await ack() 
    logger.info("app_mention")
    thread_ts = body['event']['ts']
    slack_output = await process_slack_message(app, body, logger, thread_ts)
    await say(text=slack_output)

@app.event("message")
async def handle_direct_message(ack, body, say, logger):
    await ack()
    logger.info("message")
    slack_output = await process_slack_message(app, body, logger)
    await say(text=slack_output)

@api.post('/slack/message')
async def slack(req: Request):
    return await app_handler.handle(req)

if __name__ == "__main__":
    uvicorn.run(api, port=int(os.environ.get("PORT", 8080)), host="0.0.0.0")