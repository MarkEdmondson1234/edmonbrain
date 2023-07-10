import sys, os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

# app.py
from flask import Flask, request, jsonify
import qna.question_service as qs
import qna.publish_to_pubsub_embed as pbembed
import qna.pubsub_chunk_to_store as pb
import logging

app = Flask(__name__)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

def document_to_dict(document):
    return {
        "page_content": document.page_content,
        "metadata": document.metadata
    }

def parse_output(bot_output):
    if 'source_documents' in bot_output:
        bot_output['source_documents'] = [document_to_dict(doc) for doc in bot_output['source_documents']]
    if bot_output.get("answer", None) is None or bot_output.get("answer") == "":
        bot_output['answer'] = "(No text was returned)"
    return bot_output

def create_message_element(message):
    if 'text' in message:  # This is a Slack message
        return message['text']
    else:  # This is a message in Discord format
        return message["content"]

def is_human(message):
    if 'name' in message:
        return message["name"] == "Human"
    elif 'sender' in message:  # Google Chat
        return message['sender']['type'] == 'HUMAN'
    else:
        return 'user' in message  # Slack

def is_ai(message):
    if 'name' in message:
        return message["name"] == "AI"
    elif 'sender' in message:  # Google Chat
        return message['sender']['type'] == 'BOT'
    else:
        return 'bot_id' in message  # Slack

def extract_chat_history(chat_history=None):
    
    if chat_history:
        # Separate the messages into human and AI messages
        human_messages = [create_message_element(message) for message in chat_history if is_human(message)]
        ai_messages = [create_message_element(message) for message in chat_history if is_ai(message)]
        # Pair up the human and AI messages into tuples
        paired_messages = list(zip(human_messages, ai_messages))
    else:
        print("No chat history found")
        paired_messages = []

    return paired_messages


@app.route('/qna/<vector_name>', methods=['POST'])
def process_qna(vector_name):
    data = request.get_json()
    user_input = data['user_input']
    paired_messages = extract_chat_history(data['chat_history'])
    logging.info(f'QNA got: {user_input}')
    logging.info(f'QNA got chat_history: {paired_messages}')
    try:
        bot_output = qs.qna(user_input, vector_name, chat_history=paired_messages)
        bot_output = parse_output(bot_output)
    except Exception as err:
        bot_output = {'answer': f'QNA_ERROR: An error occurred while processing /qna/{vector_name}: {str(err)}'}
    logging.info(f'==LLM Q:{user_input} - A:{bot_output["answer"]}')
    return jsonify(bot_output)

# can only take up to 10 minutes to ack
@app.route('/pubsub_chunk_to_store/<vector_name>', methods=['POST'])
def pubsub_chunk_to_store(vector_name):
    """
    Final PubSub destination for each chunk that sends data to Supabase vectorstore"""
    if request.method == 'POST':
        data = request.get_json()

        try:
            meta = pb.from_pubsub_to_supabase(data, vector_name)
            return {'status': 'Success', 'message': meta}, 200
        except Exception as err:
            logging.error(f'QNA_ERROR_EMBED: Error when sending {data} to {vector_name} pubsub_chunk_to_store: {str(err)}')
            return {'status': 'error', 'message':f'{str(err)}'}, 200



@app.route('/pubsub_to_store/<vector_name>', methods=['POST'])
def pubsub_to_store(vector_name):
    """
    splits up text or gs:// file into chunks and sends to pubsub topic 
      that pushes back to /pubsub_chunk_to_store/<vector_name>
    """
    if request.method == 'POST':
        data = request.get_json()

        try:
            meta = pbembed.data_to_embed_pubsub(data, vector_name)
            if meta is None:
                return jsonify({'status': 'ok', 'message': 'No action required'}), 201
            file_uploaded = str(meta.get("source", "Could not find a source"))
            return jsonify({'status': 'Success', 'source': file_uploaded}), 200
        except Exception as err:
            logging.error(f'QNA_ERROR_EMBED: Error when sending {data} to {vector_name} pubsub_to_store: {str(err)}')
            return {'status': 'error', 'message':f'{str(err)}'}, 200

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

