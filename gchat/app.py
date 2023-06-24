import sys, os, requests

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

# app.py
from flask import Flask, request, jsonify
import logging
from webapp import bot_help
import gchat_help

app = Flask(__name__)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

@app.route('/gchat/<vector_name>/message', methods=['POST'])
def gchat_message(vector_name):
    event = request.get_json()
    logging.info(f'gchat_event: {event}')
    if event['type'] == 'ADDED_TO_SPACE' and not event['space'].get('singleUserBotDm', False):
        text = 'Thanks for adding me to "%s"! Use !help to get started' % (event['space']['displayName'] if event['space']['displayName'] else 'this chat')
  
        return jsonify({'text': text})
    
    elif event['type'] == 'MESSAGE':
        
        gchat_help.send_to_pubsub(event, vector_name=vector_name)
        
        return jsonify({'text':'--Thinking via {vector_name}...'})
    else:
        logging.info(f"Not implemented event: {event}")
        return

@app.route('/pubsub/callback', methods=['POST'])
def gchat_send(event):
    
    bot_output, vector_name, space_id = gchat_help.process_pubsub_data(event)

    logging.info(f"bot_output: {bot_output} {vector_name}")

    # text supports code formatting, cards do not
    if vector_name  == 'codey':
        gchat_output = {'text': bot_output['answer']}
    else:
        meta_card = gchat_help.generate_google_chat_card(bot_output, how_many=1)
        gchat_output = {'cards': meta_card['cards'] }

    # send gchat_output to gchat
    gchat_help.send_to_gchat(gchat_output, space_id=space_id)

    return True


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

