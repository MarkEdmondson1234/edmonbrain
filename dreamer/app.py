from flask import Flask
import sys, os
import traceback
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
import logging
from flask import request, jsonify
from google.cloud import discoveryengine_v1
#https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.document_service.DocumentServiceClient#google_cloud_discoveryengine_v1_services_document_service_DocumentServiceClient_import_documents
from dreamer.dream import dream

app = Flask(__name__)

@app.route('/dream/<vector_name>', methods=['GET'])
def create_dream(vector_name):
    dream(vector_name)
    return {
        "message": f"Dream for vector {vector_name} created and uploaded successfully."
    }

@app.route('/import/discoveryengine/bigquery/<project_id>/<datastore_id>', methods=['POST'])
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

        client = discoveryengine_v1.DocumentServiceClient()

        # Construct the parent resource identifier
        parent = f"projects/{project_id}/locations/global/collections/default_collection/dataStores/{datastore_id}/branches/0"

        import_request = discoveryengine_v1.ImportDocumentsRequest(parent=parent)

        big_query_source = discoveryengine_v1.BigQuerySource(
                project_id=project_id,
                dataset_id=data['DATASET_ID'],
                table_id=data['TABLE_ID']
            )

        # Add optional fields to the request arguments if they are present in the POST data
        if 'DATA_SCHEMA' in data:
            big_query_source.data_schema = data['DATA_SCHEMA']
        
        import_request.bigquery_source = big_query_source

        if 'ERROR_DIRECTORY' in data:
            import_request.error_config = discoveryengine_v1.ImportErrorConfig(gcsPrefix=data['ERROR_DIRECTORY'])
        if 'RECONCILIATION_MODE' in data:
            import_request.reconciliation_mode = data['RECONCILIATION_MODE']
        if 'AUTO_GENERATE_IDS' in data:
            import_request.auto_generate_ids = data['AUTO_GENERATE_IDS']
        if 'ID_FIELD' in data:
            import_request.id_field = data['ID_FIELD']
        
        logging.info(f"Sending payload {import_request}")

        # Make the request
        operation = client.import_documents(request=import_request)

        logging.info("Waiting for operation to complete...")
        
        response = operation.result()

        # Handle the response
        logging.info(f"Response received: {response}")
        return jsonify({"response": str(response)}), 200
    
    except KeyError as e:
        logging.error(f"Missing required parameter: {str(e)}")
        return jsonify({"error": f"Missing required parameter: {str(e)}"}), 400
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    

if __name__ == '__main__':
    app.run(debug=True)
