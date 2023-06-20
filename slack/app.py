from flask import Flask, request
import logging, json
from webapp import bot_help
from qna import pubsub_manager as pubsub

# https://github.com/slackapi/bolt-python/blob/main/examples/flask/app.py
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

    # Remove mention of the bot user from user_input
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
    logging.debug('messages: {}'.format(messages))
    paired_messages = bot_help.extract_chat_history(messages)

    command_response = bot_help.handle_special_commands(user_input, vector_name, paired_messages)
    if command_response is not None:
        payload = {
            "response": command_response,
            "thread_ts": thread_ts
        }
        pubsub_manager = pubsub.PubSubManager(vector_name, pubsub_topic=f"slack_response_{vector_name}")
        pubsub_manager.publish_message(json.dumps(payload))
        return

    logging.info(f'Sending from Slack: {user_input} to {vector_name}')
    # it just gets stuck here and never progresses further
    bot_output = qs.qna(user_input, vector_name, chat_history=paired_messages)
    logger.info(f"bot_output: {bot_output}")

    slack_output = bot_output.get("answer", "No answer available")

    payload = {
        "response": slack_output,
        "thread_ts": thread_ts,
        "channel_id": body['event']['channel']  # Add the channel ID to the payload
    }
    pubsub_manager = pubsub.PubSubManager(vector_name, pubsub_topic=f"slack_response_{vector_name}")
    sub_name = f"pubsub_slack_response_{vector_name}"

    sub_exists = pubsub_manager.subscription_exists(sub_name)

    if not sub_exists:
        pubsub_manager.create_subscription(sub_name, push_endpoint="/pubsub/slack-response")

    pubsub_manager.publish_message(json.dumps(payload))

@sapp.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()

@sapp.event("app_mention")
def handle_app_mention(ack, body, say, logger):
    ack()  # immediately acknowledge the event 
    thread_ts = body['event']['ts']  # The timestamp of the original message
    process_slack_message(sapp, body, logger, thread_ts)

@sapp.event("message")
def handle_direct_message(ack, body, say, logger):
    ack()  # immediately acknowledge the event 
    process_slack_message(sapp, body, logger)


shandler = SlackRequestHandler(sapp)
@app.route('/slack/message', methods=['POST'])
def slack():
    return shandler.handle(request)

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

