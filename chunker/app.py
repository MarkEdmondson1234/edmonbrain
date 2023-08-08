import sys, os
import traceback
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

# app.py
from flask import Flask, request, jsonify
import chunker.publish_to_pubsub_embed as pbembed

import logging

app = Flask(__name__)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

@app.route('/pubsub_to_store_batch/<vector_name>', methods=['POST'])
def pubsub_to_store_batch(vector_name):
    """
    splits up text or gs:// file into chunks and sends to pubsub topic 
      that pushes back to /pubsub_chunk_to_store/<vector_name>
    """
    if request.method == 'POST':
        data = request.get_json()

        try:
            meta = pbembed.data_to_embed_pubsub(data, vector_name, batch=True)
            if meta is None:
                return jsonify({'status': 'ok', 'message': 'No action required'}), 201
            file_uploaded = str(meta.get("source", "Could not find a source"))
            return jsonify({'status': 'Success', 'source': file_uploaded}), 200
        except Exception as err:
            logging.error(f'QNA_ERROR_EMBED: Batch Error when sending {data} to {vector_name} pubsub_to_store: {str(err)} traceback: {traceback.format_exc()}')
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
            meta = pbembed.data_to_embed_pubsub(data, vector_name, batch=False)
            if meta is None:
                return jsonify({'status': 'ok', 'message': 'No action required'}), 201
            file_uploaded = str(meta.get("source", "Could not find a source"))
            return jsonify({'status': 'Success', 'source': file_uploaded}), 200
        except Exception as err:
            logging.error(f'QNA_ERROR_EMBED: Error when sending {data} to {vector_name} pubsub_to_store: {str(err)} traceback: {traceback.format_exc()}')
            return {'status': 'error', 'message':f'{str(err)}'}, 200

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

