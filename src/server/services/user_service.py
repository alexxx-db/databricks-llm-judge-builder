"""User service for retrieving current user identity."""

import logging
import os

from databricks.sdk import WorkspaceClient

from server.models import UserInfo

logger = logging.getLogger(__name__)


class UserService:
    """Service for user information from Databricks workspace."""

    def get_current_user(self) -> UserInfo:
        """Get current user information from Databricks workspace identity."""
        databricks_host = os.getenv('DATABRICKS_HOST')
        if databricks_host and not databricks_host.startswith('http'):
            databricks_host = f'https://{databricks_host}'

        service_principal_id = os.getenv('DATABRICKS_CLIENT_ID')

        try:
            w = WorkspaceClient()
            me = w.current_user.me()
            return UserInfo(
                userName=me.user_name or '',
                displayName=me.display_name or me.user_name or '',
                databricks_host=databricks_host,
                service_principal_id=service_principal_id,
            )
        except Exception as e:
            logger.warning(f'Failed to get current user from workspace, using fallback: {e}')
            return UserInfo(
                userName=os.getenv('DATABRICKS_USER', 'unknown_user'),
                displayName=os.getenv('DATABRICKS_USER', 'Unknown User'),
                databricks_host=databricks_host,
                service_principal_id=service_principal_id,
            )


# Global service instance
user_service = UserService()
