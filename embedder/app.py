import sys, os
import traceback
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

# app.py
from flask import Flask, request
import embedder.pubsub_chunk_to_store as pb

import logging

app = Flask(__name__)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

# can only take up to 10 minutes to ack
@app.route('/pubsub_chunk_to_store/<vector_name>', methods=['POST'])
def pubsub_chunk_to_store(vector_name):
    """
    Final PubSub destination for each chunk that sends data to vectorstore"""
    if request.method == 'POST':
        data = request.get_json()

        try:
            meta = pb.from_pubsub_to_vectorstore(data, vector_name)
            return {'status': 'Success', 'message': meta}, 200
        except Exception as err:
            logging.error(f'QNA_ERROR_EMBED: Error when sending {data} to {vector_name} pubsub_chunk_to_store: {str(err)} traceback: {traceback.format_exc()}')
            return {'status': 'error', 'message':f'{str(err)} traceback: {traceback.format_exc()}'}, 200

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

