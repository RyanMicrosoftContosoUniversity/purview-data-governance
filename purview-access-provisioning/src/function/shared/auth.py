"""Authentication module for Fabric and Purview API access.

Acquires OAuth tokens using SPN credentials stored in Key Vault (production)
or environment variables (local development).
"""

import logging
import os
from typing import Optional

import msal
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
PURVIEW_SCOPE = "https://purview.azure.net/.default"


class AuthenticationError(Exception):
    """Raised when token acquisition or credential retrieval fails."""


def get_spn_credentials_from_keyvault() -> dict:
    """Retrieve SPN credentials from Azure Key Vault.

    Uses the Function App's managed identity (DefaultAzureCredential) to
    authenticate to Key Vault. Falls back to environment variables for local
    development when KEY_VAULT_URI is not set.

    Returns:
        dict with keys: client_id, client_secret, tenant_id
    """
    vault_uri = os.environ.get("KEY_VAULT_URI")

    if vault_uri:
        logger.info("Fetching SPN credentials from Key Vault: %s", vault_uri)
        try:
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_uri, credential=credential)
            return {
                "client_id": client.get_secret("spn-client-id").value,
                "client_secret": client.get_secret("spn-client-secret").value,
                "tenant_id": client.get_secret("spn-tenant-id").value,
            }
        except Exception as exc:
            raise AuthenticationError(
                f"Failed to retrieve SPN credentials from Key Vault: {exc}"
            ) from exc

    # Local dev fallback
    logger.info("KEY_VAULT_URI not set — using environment variables for SPN credentials")
    client_id = os.environ.get("SPN_CLIENT_ID")
    client_secret = os.environ.get("SPN_CLIENT_SECRET")
    tenant_id = os.environ.get("SPN_TENANT_ID")

    if not all([client_id, client_secret, tenant_id]):
        raise AuthenticationError(
            "SPN credentials not found. Set KEY_VAULT_URI or "
            "SPN_CLIENT_ID / SPN_CLIENT_SECRET / SPN_TENANT_ID env vars."
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id,
    }


def _acquire_token(credentials: dict, scope: str) -> str:
    """Acquire an OAuth token via MSAL confidential client.

    Args:
        credentials: dict with client_id, client_secret, tenant_id.
        scope: The OAuth scope to request.

    Returns:
        Access token string.

    Raises:
        AuthenticationError: If token acquisition fails.
    """
    authority = f"https://login.microsoftonline.com/{credentials['tenant_id']}"
    app = msal.ConfidentialClientApplication(
        client_id=credentials["client_id"],
        client_credential=credentials["client_secret"],
        authority=authority,
    )

    result = app.acquire_token_for_client(scopes=[scope])

    if "access_token" in result:
        logger.info("Token acquired for scope: %s", scope)
        return result["access_token"]

    error_desc = result.get("error_description", result.get("error", "Unknown error"))
    raise AuthenticationError(f"Token acquisition failed for {scope}: {error_desc}")


def get_fabric_token(credentials: Optional[dict] = None) -> str:
    """Acquire an access token for the Fabric REST API.

    Args:
        credentials: SPN credentials dict. If None, credentials are loaded
                     from Key Vault or environment variables automatically.

    Returns:
        Access token string for Fabric API calls.
    """
    if credentials is None:
        credentials = get_spn_credentials_from_keyvault()
    return _acquire_token(credentials, FABRIC_SCOPE)


def get_purview_token(credentials: Optional[dict] = None) -> str:
    """Acquire an access token for the Purview REST API.

    Args:
        credentials: SPN credentials dict. If None, credentials are loaded
                     from Key Vault or environment variables automatically.

    Returns:
        Access token string for Purview API calls.
    """
    if credentials is None:
        credentials = get_spn_credentials_from_keyvault()
    return _acquire_token(credentials, PURVIEW_SCOPE)
