"""Gmail OAuth + service builder.

First-time login (opens a browser, run ONCE from the project root):
    python -m mcp_server.gmail_client

The MCP server itself never starts the browser flow, because stdout is used
for the MCP protocol and any print would corrupt it.
"""

import sys

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build

from config.settings import CREDENTIALS_FILE, SCOPES, TOKEN_FILE

_service = None


def authenticate() -> None:
    """Interactive OAuth login. Saves credentials/token.json."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Missing {CREDENTIALS_FILE}. Download the OAuth client JSON "
            "from Google Cloud Console (Desktop app) and save it there."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Saved token to {TOKEN_FILE}")


def get_auth_url(redirect_uri: str) -> tuple[str, str]:
    flow = Flow.from_client_secrets_file(str(CREDENTIALS_FILE), scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    flow.autogenerate_code_verifier = False
    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
    return auth_url, state


def fetch_token_from_code(code: str, redirect_uri: str) -> None:
    flow = Flow.from_client_secrets_file(str(CREDENTIALS_FILE), scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    flow.autogenerate_code_verifier = False
    flow.fetch_token(code=code)
    creds = flow.credentials
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Saved token to {TOKEN_FILE}")


def is_authenticated() -> bool:
    try:
        _load_credentials()
        return True
    except RuntimeError:
        return False


def _load_credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        except RefreshError:
            creds = None

    if not creds or not creds.valid:
        raise RuntimeError(
            "Gmail is not authenticated (or the token expired). "
            "Run: python -m mcp_server.gmail_client"
        )
    return creds


def get_service():
    """Return a cached Gmail API service object."""
    global _service
    if _service is None:
        _service = build(
            "gmail", "v1", credentials=_load_credentials(), cache_discovery=False
        )
    return _service


if __name__ == "__main__":
    try:
        authenticate()
    except Exception as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        sys.exit(1)
