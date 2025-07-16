import os
import yaml
import json
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import logging

class AuthManager:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.oauth_config = self.config['oauth']
        self.accounts = self.config['accounts']
        self.credentials_file = "credentials.json"
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def setup_oauth_flow(self):
        """Setup OAuth2 flow for authentication"""
        client_config = {
            "web": {
                "client_id": self.oauth_config['client_id'],
                "client_secret": self.oauth_config['client_secret'],
                "redirect_uris": [self.oauth_config['redirect_uri']],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=self.oauth_config['scopes']
        )
        flow.redirect_uri = self.oauth_config['redirect_uri']
        return flow

    def authenticate_account(self, account_name):
        """Authenticate a specific account and get refresh token"""
        self.logger.info(f"Starting authentication for {account_name}")
        
        flow = self.setup_oauth_flow()
        
        # Get authorization URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            login_hint=self.accounts[account_name]['email']
        )
        
        print(f"\nPlease visit this URL to authorize the application for {account_name}:")
        print(f"{auth_url}\n")
        
        # Get authorization code from user
        authorization_code = input("Enter the authorization code: ").strip()
        
        # Exchange code for credentials
        flow.fetch_token(code=authorization_code)
        credentials = flow.credentials
        
        # Save refresh token
        self.accounts[account_name]['refresh_token'] = credentials.refresh_token
        self._save_config()
        
        self.logger.info(f"Authentication completed for {account_name}")
        return credentials

    def get_credentials(self, account_name):
        """Get valid credentials for an account"""
        refresh_token = self.accounts[account_name].get('refresh_token')
        
        if not refresh_token:
            self.logger.warning(f"No refresh token found for {account_name}. Starting authentication...")
            return self.authenticate_account(account_name)
        
        # Create credentials from refresh token
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.oauth_config['client_id'],
            client_secret=self.oauth_config['client_secret'],
            scopes=self.oauth_config['scopes']
        )
        
        # Refresh the token if needed
        if not credentials.valid:
            credentials.refresh(Request())
        
        return credentials

    def authenticate_all_accounts(self):
        """Authenticate all accounts that don't have refresh tokens"""
        for account_name in self.accounts:
            if not self.accounts[account_name].get('refresh_token'):
                self.authenticate_account(account_name)

    def _save_config(self):
        """Save updated configuration with refresh tokens"""
        with open("config.yaml", 'w') as file:
            yaml.dump(self.config, file, default_flow_style=False)
        self.logger.info("Configuration saved with updated tokens")

    def revoke_credentials(self, account_name):
        """Revoke credentials for an account"""
        self.accounts[account_name]['refresh_token'] = None
        self._save_config()
        self.logger.info(f"Credentials revoked for {account_name}")