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

def parse_output(bot_output):
    if 'source_documents' in bot_output:
        bot_output['source_documents'] = [doc.to_dict() for doc in bot_output['source_documents']]
    return bot_output


@app.route('/qna/<vector_name>', methods=['POST'])
def process_qna(vector_name):
    data = request.get_json()
    user_input = data['user_input']
    paired_messages = data['paired_messages']
    logging.info(f'Processing {user_input}\n{paired_messages}')
    bot_output = qs.qna(user_input, vector_name, chat_history=paired_messages)
    logging.info(f'Bot output: {bot_output}')
    bot_output = parse_output(bot_output)
    logging.info(f'Bot output2: {bot_output}')
    return jsonify(bot_output)

# can only take up to 10 minutes to ack
@app.route('/pubsub_chunk_to_store/<vector_name>', methods=['POST'])
def pubsub_chunk_to_store(vector_name):
    """
    Final PubSub destination for each chunk that sends data to Supabase vectorstore"""
    if request.method == 'POST':
        data = request.get_json()

        meta = pb.from_pubsub_to_supabase(data, vector_name)

        return {'status': 'Success'}, 200


@app.route('/pubsub_to_store/<vector_name>', methods=['POST'])
def pubsub_to_store(vector_name):
    """
    splits up text or gs:// file into chunks and sends to pubsub topic 
      that pushes back to /pubsub_chunk_to_store/<vector_name>
    """
    if request.method == 'POST':
        data = request.get_json()

        meta = pbembed.data_to_embed_pubsub(data, vector_name)
        file_uploaded = str(meta.get("source", "Could not find a source"))
        return jsonify({'status': 'Success', 'source': file_uploaded}), 200

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

