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

from flask import Flask, request, jsonify
import requests
from google.auth.transport import requests as google_requests
from google.auth import default
from google.auth.transport.requests import Request

def get_google_cloud_token():
    credentials, project = default()
    auth_request = Request()
    credentials.refresh(auth_request)
    return credentials.token

@app.route('/import', methods=['POST'])
def data_import():
    # Get project config from POST data
    data = request.json

    # Get the access token
    token = get_google_cloud_token()

    # Define the endpoint and headers
    endpoint = f"https://discoveryengine.googleapis.com/v1beta/projects/{data['PROJECT_ID']}/locations/global/collections/default_collection/dataStores/{data['DATA_STORE_ID']}/branches/0/documents:import"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Define the payload
    payload = {
        "bigquerySource": {
            "projectId": data['PROJECT_ID'],
            "datasetId": data['DATASET_ID'],
            "tableId": data['TABLE_ID'],
            "dataSchema": data['DATA_SCHEMA'],
        },
        "reconciliationMode": data['RECONCILIATION_MODE'],
        "autoGenerateIds": data['AUTO_GENERATE_IDS'],
        "idField": data['ID_FIELD'],
        "errorConfig": {
            "gcsPrefix": data['ERROR_DIRECTORY']
        }
    }

    # Make the POST request
    response = requests.post(endpoint, headers=headers, json=payload)

    # Return the response
    return jsonify(response.json()), response.status_code


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

