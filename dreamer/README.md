# Dream

Takes last 10 rows and makes a dream about them.

Needs BigQuery Job User and BigQuery Data Owner added to service email IAM

## Enterprise Search Refresh

### Data Import Endpoint

The data import endpoint allows you to import data from a BigQuery table into your Generative AI App Builder.

#### Endpoint:

```
POST /import/<project_id>/<datastore_id>
```

#### Parameters

    project_id: (path parameter) The ID of your Google Cloud project.
    datastore_id: (path parameter) The ID of your data store.

#### Request Body (JSON)

Mandatory Fields:

    DATASET_ID: The name of your BigQuery dataset.
    TABLE_ID: The name of your BigQuery table.

Optional Fields:

    DATA_SCHEMA: (optional) The data schema to use, can be "document" or "custom". Default is "document".
    RECONCILIATION_MODE: (optional) The reconciliation mode to use, can be "FULL" or "INCREMENTAL". Default is "INCREMENTAL".
    AUTO_GENERATE_IDS: (optional) Whether to automatically generate document IDs. Relevant when DATA_SCHEMA is set to "custom".
    ID_FIELD: (optional) The field that represents the document IDs. Relevant when AUTO_GENERATE_IDS is false or unspecified and DATA_SCHEMA is "custom".
    ERROR_DIRECTORY: (optional) A GCS directory for error information about the import. Recommended to leave empty for automatic directory creation by Gen App Builder.

#### Example Request

Using curl:

```sh

curl -X POST \
-H "Content-Type: application/json" \
-d '{
  "DATASET_ID": "your_dataset_id",
  "TABLE_ID": "your_table_id",
  "DATA_SCHEMA": "document",
  "RECONCILIATION_MODE": "INCREMENTAL",
  "AUTO_GENERATE_IDS": false,
  "ID_FIELD": "your_id_field",
  "ERROR_DIRECTORY": "gs://your-gcs-bucket/directory/import_errors"
}' "http://localhost:8080/import/your_project_id/your_datastore_id"
```

In Python using requests library:

```python

import requests

url = "http://localhost:8080/import/your_project_id/your_datastore_id"
data = {
    "DATASET_ID": "your_dataset_id",
    "TABLE_ID": "your_table_id",
    "DATA_SCHEMA": "document",
    "RECONCILIATION_MODE": "INCREMENTAL",
    "AUTO_GENERATE_IDS": False,
    "ID_FIELD": "your_id_field",
    "ERROR_DIRECTORY": "gs://your-gcs-bucket/directory/import_errors"
}
headers = {
    "Content-Type": "application/json"
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

#### Response

The API will return the response from the Generative AI App Builder endpoint, including any errors that occurred during the data import.