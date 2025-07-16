

import os
import json
from google_auth_oauthlib.flow import Flow

# This is the scope required to read Google Analytics data.
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

def main():
    """
    Performs the OAuth 2.0 flow to get user credentials and saves them.
    """
    client_secrets_file = "client_secret.json"

    if not os.path.exists(client_secrets_file):
        print(f"Error: {client_secrets_file} not found. Please download it from your Google Cloud project and place it in the same directory as this script.")
        return

    print("=== Vision Source GA4 Authentication ===")
    token_identifier = input("Enter a unique identifier for this account (e.g., lux1, lux2, lux3, lux4): ")
    token_path = f"token_{token_identifier}.json"

    if os.path.exists(token_path):
        print(f"Token file {token_path} already exists. Please choose a different identifier or delete the existing file.")
        return

    # Read the client secrets file
    with open(client_secrets_file, 'r') as f:
        client_config = json.load(f)

    # Create the flow using the web client configuration
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES
    )
    
    # Set redirect URI to match the one configured in Google Cloud Console
    flow.redirect_uri = "http://localhost:3000/api/auth/callback/google"

    # Get the authorization URL
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    print(f"\nPlease visit this URL to authorize the application:")
    print(f"{auth_url}")
    print("\nAfter authorizing, you'll be redirected to a page that may show an error.")
    print("Copy the ENTIRE URL from your browser's address bar and paste it here.")
    
    # Get the full callback URL from user
    callback_url = input("\nPaste the full callback URL here: ").strip()
    
    # Extract the authorization code from the callback URL
    if "code=" in callback_url:
        import urllib.parse
        parsed_url = urllib.parse.urlparse(callback_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        authorization_code = query_params.get('code', [None])[0]
        
        if authorization_code:
            # Exchange code for credentials
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials

            # Save the credentials for the next run
            with open(token_path, "w") as token_file:
                token_file.write(credentials.to_json())

            print(f"\nAuthentication successful! Credentials saved to {token_path}")
        else:
            print("Error: Could not extract authorization code from URL")
    else:
        print("Error: Invalid callback URL. Please make sure you copied the entire URL.")

if __name__ == "__main__":
    main()

