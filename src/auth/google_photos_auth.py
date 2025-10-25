"""
Google Photos API authentication and authorization.
"""

import json
import pickle
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pydantic import BaseModel

# The scope for the new Photo Picker API (post-March 2025)
SCOPES = ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]
DISCOVERY_SERVICE_URL = "https://photoslibrary.googleapis.com/$discovery/rest?version=v1"

auth_router = APIRouter(tags=["auth"])


class SessionData(BaseModel):
    """Session data model for storing user session information."""

    credentials: Optional[str] = None
    picker_session_id: Optional[str] = None


class GooglePhotosAPI:
    """
    Google Photos API client with OAuth2 authentication.

    Handles authentication flow and service creation for Google Photos Library API.
    """

    def __init__(
        self,
        api_name: str = "photoslibrary",
        client_secret_file: Optional[str] = None,
        api_version: str = "v1",
        scopes: list[str] = None,
    ):
        """
        Initialize Google Photos API client.

        Args:
            api_name: Name of the Google API
            client_secret_file: Path to OAuth2 client secrets file
            api_version: API version to use
            scopes: List of OAuth2 scopes to request
        """
        self.api_name = api_name
        self.client_secret_file = client_secret_file or "credentials/client_secrets.json"
        self.api_version = api_version
        self.scopes = scopes or SCOPES

        credentials_dir = Path("./credentials")
        credentials_dir.mkdir(exist_ok=True)
        self.cred_pickle_file = credentials_dir / f"token_{self.api_name}_{self.api_version}.pickle"
        self.cred = None

    def run_local_server(self) -> Credentials:
        """
        Authenticate using OAuth2 flow and return credentials.

        Returns:
            OAuth2 credentials object
        """
        # Check if there is already a pickle file with relevant credentials
        if self.cred_pickle_file.exists():
            with open(self.cred_pickle_file, "rb") as token:
                self.cred = pickle.load(token)

        # If there is no pickle file with stored credentials, create one
        if not self.cred or not self.cred.valid:
            if self.cred and self.cred.expired and self.cred.refresh_token:
                self.cred.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_file, self.scopes
                )
                self.cred = flow.run_local_server(port=0)

            with open(self.cred_pickle_file, "wb") as token:
                pickle.dump(self.cred, token)

        return self.cred

    def get_service(self):
        """
        Build and return the Google Photos API service.

        Returns:
            Google Photos API service object
        """
        if not self.cred:
            self.run_local_server()
        return build(self.api_name, self.api_version, credentials=self.cred, static_discovery=False)

    @staticmethod
    def credentials_from_json(json_str: str) -> Credentials:
        """
        Recreate credentials from JSON string.

        Args:
            json_str: JSON string containing credential data

        Returns:
            OAuth2 credentials object
        """
        data = json.loads(json_str)
        return Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes"),
        )


# Session management helper functions
def get_session_id(request: Request, sessions: dict) -> str:
    """
    Get or create a session ID for the request.

    Args:
        request: FastAPI request object
        sessions: Dictionary of active sessions

    Returns:
        Session ID string
    """
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        session_id = secrets.token_urlsafe(32)
        sessions[session_id] = SessionData()
    return session_id


def get_session_data(session_id: str, sessions: dict) -> SessionData:
    """
    Get session data for a session ID.

    Args:
        session_id: Session identifier
        sessions: Dictionary of active sessions

    Returns:
        SessionData object
    """
    if session_id not in sessions:
        sessions[session_id] = SessionData()
    return sessions[session_id]


@auth_router.get("/auth")
async def auth(request: Request):
    """
    Authenticate with Google Photos using OAuth2 flow.

    Initiates OAuth2 flow and stores credentials in session.
    """
    try:
        api = GooglePhotosAPI()
        creds = api.run_local_server()

        # Get or create session
        session_id = get_session_id(request, auth_router.sessions)
        session_data = get_session_data(session_id, auth_router.sessions)

        # Store credentials in session
        session_data.credentials = creds.to_json()

        # Create response with session cookie
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=3600 * 24,  # 24 hours
        )
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@auth_router.get("/api/check-auth")
async def check_auth(request: Request, response: Response):
    """
    Check if user is authenticated.

    Returns authentication status for the current session.
    """
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in auth_router.sessions:
        # Clear invalid session cookie
        response.delete_cookie("session_id")
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = auth_router.sessions[session_id]
    if session_data.credentials:
        return {"authenticated": True}

    # Clear invalid session cookie
    response.delete_cookie("session_id")
    raise HTTPException(status_code=401, detail="Not authenticated")
