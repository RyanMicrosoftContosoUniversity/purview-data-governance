import requests
import json
import time
from datetime import datetime, timedelta, timezone
import logging
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Load environment variables from .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(script_dir, 'fabric_audit_env.env')
load_dotenv(env_file)

# configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("fabric_audit_polling.log"), logging.StreamHandler()]
)


# Load environment variables
TENANT_ID = os.getenv('TENANT_ID')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
AZURE_BLOB_CONNECTION_STRING = os.getenv('AZURE_BLOB_CONNECTION_STRING')
AZURE_BLOB_CONTAINER = os.getenv('AZURE_BLOB_CONTAINER')


def get_access_token():
    """
    Obtain OAuth token for 0365 Management API
    """
    token_url = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/token'
    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "resource": "https://manage.office.com",
        "grant_type": "client_credentials"
    }

    try:
        response = requests.post(token_url, data=token_data, timeout=10)
        response.raise_for_status()
        token = response.json().get('access_token')
        logging.info("Successfully obtained access token.")
        logging.debug(f"Token (first 50 chars): {token[:50] if token else 'None'}...")
        return token
    except requests.exceptions.RequestException as e:
        logging.error(f"Error obtaining access token: {e}")
        logging.error(f"Response: {e.response.text if hasattr(e, 'response') and e.response else 'N/A'}")
        return None

def ensure_subscription(access_token: str):
    """
    Ensure subscription to Audit.General content type
    
    :param access_token: Description
    :type access_token: str
    """
    subscription_url = f'https://manage.office.com/api/v1.0/{TENANT_ID}/activity/feed/subscriptions/start?contentType=Audit.General'

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(subscription_url, headers=headers, timeout=10)

        if response.status_code in [200, 201, 204]:
            logging.info("Successfully ensured subscription to Audit.General.")
        elif response.status_code == 401:
            logging.error(f"Unauthorized (401): {response.text}")
            logging.error("Check: TENANT_ID, CLIENT_ID, CLIENT_SECRET in your .env file")
        elif response.status_code == 403:
            logging.warning(f"Subscription requires admin consent (403). Response: {response.text}")
            logging.info("Proceeding to fetch audit logs - subscription may already be active.")
        else:
            logging.warning(f"Subscription response: {response.status_code} - {response.text}")
            logging.info("Proceeding with audit log collection.")
    except Exception as e:
        logging.warning(f"Subscription check failed: {e}")
        logging.info("Proceeding to fetch audit logs - subscription may already be active.")

def list_available_content(access_token:str, start_time: str, end_time:str):
    """
    List available content blobs for the time window
    
    :param access_token: Description
    :type access_token: str
    :param start_time: Description
    :type start_time: str
    :param end_time: Description
    :type end_time: str
    """
    list_url = f"https://manage.office.com/api/v1.0/{TENANT_ID}/activity/feed/subscriptions/content"
    params = {
        "contentType": "Audit.General",
        "startTime": start_time,
        "endTime": end_time
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(list_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        content_blobs = response.json()
        logging.info(f"Retrieved {len(content_blobs)} content blobs for {start_time} to {end_time}.")
        return content_blobs
    except Exception as e:
        logging.error(f"Error listing available content: {e}")
        return []

def download_content_blob(content_uri:str, access_token:str):
    """
    Download and parse a content blob
    
    :param content_uri: Description
    :type content_uri: str
    :param access_token: Description
    :type access_token: str
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(content_uri, headers=headers, timeout=10)
        response.raise_for_status()
        events = response.json()
        logging.info(f"Successfully downloaded content blob from {content_uri}.")
        return events
    except Exception as e:
        logging.error(f"Error downloading content blob: {e}")
        return []

def write_to_blob_storage(events:list, connection_string:str, container_name:str):
    """
    Write events to Azure Blob Storage
    
    :param events: List of audit events
    :type events: list
    :param connection_string: Azure Blob Storage connection string
    :type connection_string: str
    :param container_name: Name of the blob container
    :type container_name: str
    """
    blob_client = BlobServiceClient.from_connection_string(connection_string)
    container = blob_client.get_container_client(container_name)

    blob_name = f"audit-logs/{datetime.now().isoformat()}.json"
    container.upload_blob(blob_name, json.dumps(events), overwrite=True)

    logging.info(f"Written {len(events)} events to blob storage: {blob_name}")

def main():
    """
    Main execution loop
    """
    logging.info("Starting Fabric audit log ingestion")

    # get access token
    access_token = get_access_token()

    # ensure subscription is active
    ensure_subscription(access_token)

    # define time window (last 15 minutes to handle delays)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=600)

    start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")

    # list available content
    content_blobs = list_available_content(access_token, start_str, end_str)

    # process each content blob
    total_events = 0
    for blob in content_blobs:
        content_uri = blob.get("contentUri")
        if content_uri:
            events = download_content_blob(content_uri, access_token)
            ### this is where you'd send to splunk
            write_to_blob_storage(events, AZURE_BLOB_CONNECTION_STRING, AZURE_BLOB_CONTAINER)
            total_events += len(events)
    logging.info(f"Processed a total of {total_events} events from Fabric audit logs.")

if __name__ == "__main__":
    main()