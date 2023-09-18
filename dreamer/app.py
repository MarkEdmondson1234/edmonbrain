from flask import Flask
import sys, os
import traceback
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
import logging
from flask import request, jsonify
import requests
from google.auth import default
from google.auth.transport.requests import Request

from dreamer.dream import dream

app = Flask(__name__)

@app.route('/dream/<vector_name>', methods=['GET'])
def create_dream(vector_name):
    dream(vector_name)
    return {
        "message": f"Dream for vector {vector_name} created and uploaded successfully."
    }



def get_google_cloud_token():
    logging.info("Getting google cloud token...")
    credentials, project = default()
    auth_request = Request()
    credentials.refresh(auth_request)
    logging.info("Got token")
    return credentials.token

@app.route('/import/<project_id>/<datastore_id>', methods=['POST'])
def data_import(project_id, datastore_id):
    """
    Endpoint to initiate data import from BigQuery to Generative AI App Builder.

    Parameters in URL:
    - project_id: The ID of your GCP project
    - datastore_id: The ID of your data store

    JSON Parameters (POST):
    - DATASET_ID: The name of your BigQuery dataset
    - TABLE_ID: The name of your BigQuery table

    Optional JSON Parameters (POST):
    - DATA_SCHEMA: Values are "document" (default) and "custom".
    - RECONCILIATION_MODE: Values are "FULL" and "INCREMENTAL" (default).
    - AUTO_GENERATE_IDS: Specifies whether to automatically generate document IDs (relevant when DATA_SCHEMA is set to "custom").
    - ID_FIELD: Specifies which field represents the document IDs (relevant when AUTO_GENERATE_IDS is false or unspecified and DATA_SCHEMA is "custom").
    - ERROR_DIRECTORY: A GCS directory for error information about the import. Recommended to leave empty for automatic directory creation by Gen App Builder.

    Refer to the API documentation for more details on the optional parameters and their usage.
    https://cloud.google.com/generative-ai-app-builder/docs/refresh-data#discoveryengine_v1_generated_DocumentService_RefreshStructured_sync-drest
    """
    
    # Get project config from POST data
    try:
        data = request.json

        # Get the access token
        token = get_google_cloud_token()

        # Define the endpoint and headers
        endpoint = f"https://discoveryengine.googleapis.com/v1beta/projects/{project_id}/locations/global/collections/default_collection/dataStores/{datastore_id}/branches/0/documents:import"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Define the payload with mandatory fields
        payload = {
            "bigquerySource": {
                "projectId": project_id,
                "datasetId": data['DATASET_ID'],
                "tableId": data['TABLE_ID'],
            }
        }
        
        # Add optional fields to the payload if they are present in the POST data
        bigquery_source = payload['bigquerySource']
        if 'DATA_SCHEMA' in data:
            bigquery_source['dataSchema'] = data['DATA_SCHEMA']
        if 'ERROR_DIRECTORY' in data:
            payload['errorConfig'] = {"gcsPrefix": data['ERROR_DIRECTORY']}
        if 'RECONCILIATION_MODE' in data:
            payload['reconciliationMode'] = data['RECONCILIATION_MODE']
        if 'AUTO_GENERATE_IDS' in data:
            payload['autoGenerateIds'] = data['AUTO_GENERATE_IDS']
        if 'ID_FIELD' in data:
            payload['idField'] = data['ID_FIELD']

        logging.info(f"Sending payload {payload} to {endpoint}")
        # Make the POST request
        response = requests.post(endpoint, headers=headers, json=payload)
        logging.info(f"Sent payload {payload} to {endpoint}")
        # Return the response
        return jsonify(response.json()), response.status_code

    except KeyError as e:
        logging.error(f"Missing required parameter: {str(e)}")
        return jsonify({"error": f"Missing required parameter: {str(e)}}"), 400

    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}}"), 500


if __name__ == '__main__':
    app.run(debug=True)
