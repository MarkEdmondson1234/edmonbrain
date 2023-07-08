import sys, os
import traceback

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

# app.py
from flask import Flask, request, jsonify
import logging
import gchat_help

app = Flask(__name__)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

@app.route('/gchat/<vector_name>/message', methods=['POST'])
def gchat_message(vector_name):
    event = request.get_json()
    logging.info(f'gchat_event: {event}')
    if event['type'] == 'ADDED_TO_SPACE' and not event['space'].get('singleUserBotDm', False):
        text = 'Thanks for adding me to "%s"! Use `!help` to get started' % (event['space']['displayName'] if event['space']['displayName'] else 'this chat')
  
        return jsonify({'text': text})
    
    elif event['type'] == 'MESSAGE':
        
        gchat_help.send_to_pubsub(event, vector_name=vector_name)

        space_id = event['space']['name']
        user_name = event['message']['sender']['displayName']

        logging.info(f"Received from {space_id}:{user_name}")
        
        return jsonify({'text':"Thinking..."})
    else:
        logging.info(f"Not implemented event: {event}")
        return

@app.route('/pubsub/callback', methods=['POST'])
def gchat_send():

    if request.method != 'POST':
        return "Unsupported method", 404
    
    event = request.get_json()    
    
    try:
        bot_output, vector_name, space_id = gchat_help.process_pubsub_data(event)
    except Exception as err:
        error_message = traceback.format_exc()        
        gchat_output = {'text': f'Error in process_pubsub_data: {str(err)} {error_message}'}
        logging.error(gchat_output)
        return gchat_output

    logging.info(f"bot_output: {bot_output} {vector_name}")
    
    if bot_output.get("result", None) != None:
        # result from !slash commands
        gchat_output = {'text': bot_output["result"]}
    
    elif vector_name  == 'codey':
        # text supports code formatting, cards do not
        gchat_output = {'text': bot_output['answer']}
    else:
        meta_card = gchat_help.generate_google_chat_card(bot_output, how_many=1)
        gchat_output = {'cards': meta_card['cards'] }

    # send gchat_output to gchat
    gchat_help.send_to_gchat(gchat_output, space_id=space_id)

    return "Ok"


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

