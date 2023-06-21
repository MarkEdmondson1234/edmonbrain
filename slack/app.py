import sys, os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from flask import Flask, request
import logging
from webapp import bot_help

from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

sapp = App()

app = Flask(__name__)

def process_slack_message(sapp, body, logger, thread_ts=None):
    logger.info(body)
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

    chat_historys = sapp.client.conversations_replies(
        channel=body['event']['channel'],
        ts=thread_ts
    ) if thread_ts else sapp.client.conversations_history(
        channel=body['event']['channel']
    )

    messages = chat_historys['messages']
    
    command_response = bot_help.handle_special_commands(user_input, vector_name, messages)
    if command_response is not None:
        return command_response['result']

    logging.info(f'Sending from Slack: {user_input} to {vector_name}')
    bot_output = bot_help.send_to_qa(user_input, vector_name, chat_history=messages)
    logging.info(f"Slack bot_output: {bot_output}")

    slack_output = bot_output.get("answer", "No answer available")

    return slack_output

@sapp.middleware  
def log_request(logger, body, next):
    logger.debug(body)
    return next()

@sapp.event("app_mention")
def handle_app_mention(ack, body, say, logger):
    ack() 
    thread_ts = body['event']['ts']
    say(process_slack_message(sapp, body, logger, thread_ts))

@sapp.event("message")
def handle_direct_message(ack, body, say, logger):
    ack()
    say(process_slack_message(sapp, body, logger))


shandler = SlackRequestHandler(sapp)
@app.route('/slack/message', methods=['POST'])
def slack():
    return shandler.handle(request)

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
