import sys, os
# https://github.com/slackapi/bolt-python/blob/main/examples/fastapi/async_app.py
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import uvicorn
from fastapi import FastAPI, Request
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
import slack.slack_help as slack_help

app = AsyncApp()
app_handler = AsyncSlackRequestHandler(app)

api = FastAPI()

@app.event("message")
async def handle_private_message(ack, body, say, logger):
    channel_type = body['event']['channel_type']
    if channel_type == 'im': # Respond only if the message is a direct message
        logger.info(body)
        await ack()
        thread_ts = body['event']['ts']
        slack_output = await slack_help.process_slack_message(app, body, logger, thread_ts)
        await say(text=slack_output, thread_ts=thread_ts)

@app.event("app_mention")
async def handle_app_mention(ack, body, say, logger):
    await ack() 
    logger.info("app_mention")
    thread_ts = body['event']['ts']
    slack_output = await slack_help.process_slack_message(app, body, logger, thread_ts)
    await say(text=slack_output, thread_ts=thread_ts)


@api.post('/slack/message')
async def slack(req: Request):
    return await app_handler.handle(req)

if __name__ == "__main__":
    uvicorn.run(api, port=int(os.environ.get("PORT", 8080)), host="0.0.0.0")