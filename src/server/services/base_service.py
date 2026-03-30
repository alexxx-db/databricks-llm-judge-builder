"""Base service class with shared authentication and MLflow setup."""

import os
import logging

import mlflow
from dotenv import load_dotenv
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

# Module-level shared client
_shared_mlflow_client = None


def get_shared_mlflow_client():
    """Get the shared MLflow client instance."""
    global _shared_mlflow_client
    
    if _shared_mlflow_client is None:
        # Load env and validate auth
        load_dotenv('.env.local')
        _validate_auth()
            
        # Setup MLflow once
        mlflow.set_tracking_uri('databricks')
        _shared_mlflow_client = MlflowClient()
        
    return _shared_mlflow_client


def _validate_auth():
    """Validate Databricks authentication credentials.

    Raises RuntimeError if no valid authentication configuration is found,
    unless running inside a Databricks App (where credentials are injected
    automatically and env vars may not be set at import time).
    """
    databricks_host = os.getenv('DATABRICKS_HOST')
    databricks_token = os.getenv('DATABRICKS_TOKEN')
    databricks_client_id = os.getenv('DATABRICKS_CLIENT_ID')
    databricks_client_secret = os.getenv('DATABRICKS_CLIENT_SECRET')
    databricks_config_profile = os.getenv('DATABRICKS_CONFIG_PROFILE')

    has_token_auth = databricks_host and databricks_token
    has_oauth_auth = databricks_host and databricks_client_id and databricks_client_secret
    has_profile = bool(databricks_config_profile)

    # Inside Databricks Apps, credentials are injected via the runtime — env vars
    # may not be present at startup. Also accept a configured CLI profile.
    if not (has_token_auth or has_oauth_auth or has_profile):
        logger.warning(
            'No Databricks authentication found via env vars or CLI profile. '
            'If running inside Databricks Apps, credentials will be injected automatically. '
            'Otherwise set DATABRICKS_HOST and '
            '(DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID+DATABRICKS_CLIENT_SECRET) '
            'or DATABRICKS_CONFIG_PROFILE.'
        )


class BaseService:
    """Base service class with shared MLflow client."""

    def __init__(self):
        # Use shared client instead of creating individual instances
        self.client = get_shared_mlflow_client()
