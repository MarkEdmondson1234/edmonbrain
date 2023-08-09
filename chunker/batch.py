import os
import json
import requests

def create_and_execute_batch_job(gs_file, vector_name, metadata):
    from google.cloud import batch_v1
    client = batch_v1.BatchServiceClient()

    meta_str = json.dumps(metadata)

    # https://cloud.google.com/batch/docs/create-run-basic-job
    runnable = batch_v1.Runnable()
    runnable.environment = batch_v1.Environment()
    #runnable.environment.secret_variables = {"QNA_URL": "projects/gcloud-brain/secrets/QNA_URL/versions/latest",
    #                                         "GIT_PAT": "projects/gcloud-brain/secrets/GIT_PAT/versions/latest",
    #                                         "PGVECTOR_CONNECTION_STRING": "projects/gcloud-brain/secrets/PGVECTOR_CONNECTION_STRING/versions/latest"}
    #runnable.environment.variables = {"GCS_BUCKET": os.getenv("GCS_BUCKET")}
    # hard code this for now as it doesn't see to see otherwise.
    runnable.environment.variables = {"QNA_URL": os.getenv("QNA_URL", "BATCH_NOT_FOUND"),
                                      "GIT_PAT": os.getenv("GIT_PATH", "BATCH_NOT_FOUND"),
                                      "PGVECTOR_CONNECTION_STRING": os.getenv("PGVECTOR_CONNECTION_STRING","BATCH_NOT_FOUND"),
                                      "UNSTRUCTURED_URL": os.getenv("UNSTRUCTURED_URL", "BATCH_NOT_FOUND"),
                                      "EMBED_URL": os.getenv("EMBED_URL", "BATCH_NOT_FOUND"),
                                      "GCS_BUCKET": os.getenv("GCS_BUCKET", "BATCH_NOT_FOUND")}

    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = os.getenv("THIS_IMAGE", "BATCH_NOT_FOUND")
    runnable.container.commands=["python", "chunker/batch.py",
                                 gs_file, vector_name, meta_str]

    task = batch_v1.TaskSpec()
    task.runnables = [runnable]

    # We can specify what resources are requested by each task.
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 2000  # in milliseconds per cpu-second. This means the task requires 2 whole CPUs.
    resources.memory_mib = 20480  # in MiB - 10GiB
    task.compute_resource = resources

    task.max_retry_count = 3
    task.max_run_duration = "10800s" # 3hrs

    # Tasks are grouped inside a job using TaskGroups.
    # Currently, it's possible to have only one task group.
    group = batch_v1.TaskGroup()
    group.task_count = 1
    group.task_spec = task

    # Policies are used to define on what kind of virtual machines the tasks will run on.
    # In this case, we tell the system to use "e2-standard-4" machine type.
    # Read more about machine types here: https://cloud.google.com/compute/docs/machine-types
    policy = batch_v1.AllocationPolicy.InstancePolicy()
    policy.machine_type = "e2-standard-4"
    instances = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instances.policy = policy
    allocation_policy = batch_v1.AllocationPolicy()
    allocation_policy.instances = [instances]
    allocation_policy.service_account = batch_v1.ServiceAccount(
        email=get_service_account_email())

    job = batch_v1.Job()
    job.task_groups = [group]
    job.allocation_policy = allocation_policy
    job.labels = {"env": "gcloud-brain", "type": "container"}
    # We use Cloud Logging as it's an out of the box available option
    job.logs_policy = batch_v1.LogsPolicy()
    job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING

    job_id = valid_batch_id(gs_file)
    create_request = batch_v1.CreateJobRequest()
    create_request.job = job
    create_request.job_id = job_id
    create_request.parent = f"projects/{get_gcp_project()}/locations/europe-west3"

    # Make the request
    client.create_job(create_request)

    logging.info(f"Created batch jobId: {job_id} for {gs_file} {vector_name} {metadata}")
    # Handle the response
    return job_id

def valid_batch_id(input_string:str):
    import re
    import datetime
    job_id = re.sub(r'gs://', '', input_string)
    # Remove unwanted parts of the string
    # Replace '/' and '_' with '-'
    job_id = re.sub(r'[/_]', '-', job_id)

    # Remove any characters that are not lowercase letters, numbers, or hyphens
    job_id = re.sub(r'[^a-z0-9-]', '', job_id.lower())

    # Replace uppercase letters with lowercase
    job_id = job_id.lower()

    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    # Append the timestamp to the job_id
    job_id = f"eb-{timestamp}-{job_id}"

    # Check the length of the Job ID, if it exceeds 63 characters, truncate it
    if len(job_id) > 60:
        job_id = job_id[:60]

    return job_id

def get_service_account_email():
    return get_metadata('instance/service-accounts/default/email')

def get_gcp_project():
    return get_metadata('project/project-id')

def get_metadata(stem):
    
    metadata_server_url = f'http://metadata.google.internal/computeMetadata/v1/{stem}'

    headers = {'Metadata-Flavor': 'Google'}

    response = requests.get(metadata_server_url, headers=headers)

    if response.status_code == 200:
        return response.text
    else:
        print(f"Request failed with status code {response.status_code}")
        return None



if __name__ == "__main__":
    import sys
    import logging
    from chunker.publish_to_pubsub_embed import chunk_doc_to_docs
    from chunker.publish_to_pubsub_embed import process_docs_chunks_vector_name
    from chunker.loaders import read_file_to_document

    # Get arguments from command line
    gs_file = sys.argv[1]
    vector_name = sys.argv[2]
    metadata = sys.argv[3]

    
    logging.info("Start batch chunker for {gs_file} to {vector_name}")
    docs = read_file_to_document(gs_file, vector_name, metadata)
    logging.info("Finished batch chunker for {gs_file} to {vector_name}")

    chunks = chunk_doc_to_docs(docs)

    logging.info("Sending chunks to embed for {gs_file} to {vector_name}")
    process_docs_chunks_vector_name(chunks, vector_name, metadata)
    logging.info("Finished sending chunks to embed for {gs_file} to {vector_name}")