import os, sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import requests

def get_service_account_email():
    return get_metadata('instance/service-accounts/default/email')

def get_gcp_project():
    return get_metadata('project/project-id')

def get_region():
    # The "instance/zone" metadata includes the region as part of the zone name
    zone = get_metadata('instance/zone')
    if zone:
        # Split by '/' and take the last part, then split by '-' and take all but the last part
        region_zone = zone.split('/')[-1]
        region = '-'.join(region_zone.split('-')[:-1])
        return region
    return None

def get_metadata(stem):
    
    metadata_server_url = f'http://metadata.google.internal/computeMetadata/v1/{stem}'

    headers = {'Metadata-Flavor': 'Google'}

    response = requests.get(metadata_server_url, headers=headers)

    if response.status_code == 200:
        return response.text
    else:
        print(f"Request failed with status code {response.status_code}")
        return None
