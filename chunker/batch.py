import os

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
                                      "GCS_BUCKET": os.getenv("GCS_BUCKET", "BATCH_NOT_FOUND")}

    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = "gcr.io/gcloud-brain/gcloudbrain/qna:latest"
    runnable.container.commands=["python", "qna/batch.py",
                                 gs_file, vector_name, meta_str]

    task = batch_v1.TaskSpec()
    task.runnables = [runnable]

    # We can specify what resources are requested by each task.
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 2000  # in milliseconds per cpu-second. This means the task requires 2 whole CPUs.
    resources.memory_mib = 20480  # in MiB - 10GiB
    task.compute_resource = resources

    task.max_retry_count = 3
    task.max_run_duration = "6600s"

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
        email="gcloud-brain-app@gcloud-brain.iam.gserviceaccount.com")

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
    create_request.parent = "projects/gcloud-brain/locations/europe-west3"

    # Make the request
    response = client.create_job(create_request)

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
    import requests
    metadata_server_url = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email'

    headers = {'Metadata-Flavor': 'Google'}

    response = requests.get(metadata_server_url, headers=headers)

    if response.status_code == 200:
        return response.text
    else:
        print(f"Request failed with status code {response.status_code}")
        return None

print(get_service_account_email())
