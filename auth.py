import base64
import hashlib
import html
import json
import os
import re
import urllib.parse
import requests

LOGIN_PROVIDER = "https://auth.digital.panasonic.com"
REDIRECT_URI = "auth0://auth.digital.panasonic.com/android/com.panasonic.SmartLaundry/callback"
CLIENT_ID = "2wSeRcOi0MoAv5ByV1tSUusr5VW3CP4v"
USERNAME = "hello@world.com"
PASSWORD = "password"


def get_authorization_code():
    session = requests.Session()

    # Generate PKCE parameters
    code_verifier = re.sub('[^a-zA-Z0-9]+', '', base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8'))
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode('utf-8').replace('=', '')
    nonce = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
    state = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')

    print(f"[Step 1] Getting authorization page...")
    # Step 1: Get authorization page
    resp = session.get(
        url=LOGIN_PROVIDER + "/authorize",
        params={
            "response_type": "code",
            "client_id": CLIENT_ID,
            "tenant": "pdpauth-a1",
            "redirect_uri": REDIRECT_URI,
            "scope": "openid offline_access smartlaundry.control offline_access",
            "audience": "https://club.panasonic.jp/" + CLIENT_ID + "/api/v1/",
            "connection": "CLUBPanasonic-Authentication",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "_intstate": "deprecated"
        },
        allow_redirects=True
    )

    # Extract CSRF token from base64-encoded config
    config_match = re.search(r"window\.atob\('([^']+)'\)", resp.text)
    config = json.loads(base64.b64decode(config_match.group(1)).decode('utf-8'))
    csrf_token = config['extraParams']['_csrf']
    print(f"  CSRF token: {csrf_token}")

    print(f"[Step 2] Posting credentials...")
    # Step 2: Post credentials
    resp = session.post(
        url=LOGIN_PROVIDER + "/usernamepassword/login",
        json={
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "tenant": "pdpauth-a1",
            "response_type": "code",
            "scope": "openid offline_access smartlaundry.control offline_access",
            "audience": "https://club.panasonic.jp/" + CLIENT_ID + "/api/v1/",
            "_csrf": csrf_token,
            "state": config['extraParams']['state'],
            "_intstate": "deprecated",
            "nonce": config['extraParams']['nonce'],
            "username": USERNAME,
            "password": PASSWORD,
            "connection": "CLUBPanasonic-Authentication",
            "captcha": None
        }
    )

    # Extract form data from response
    wa = re.search(r'name="wa"[^>]*value="([^"]+)"', resp.text).group(1)
    wresult = re.search(r'name="wresult"[^>]*value="([^"]+)"', resp.text).group(1)
    wctx = html.unescape(re.search(r'name="wctx"[^>]*value="([^"]+)"', resp.text).group(1))
    print(f"  Login successful, extracted form data")

    print(f"[Step 3] Submitting form and following redirects...")
    # Step 3: Submit form and follow redirects
    resp = session.post(
        LOGIN_PROVIDER + "/login/callback",
        data={"wa": wa, "wresult": wresult, "wctx": wctx},
        allow_redirects=False
    )

    resp = session.get(LOGIN_PROVIDER + resp.headers['Location'], allow_redirects=False)
    redirect = resp.headers['Location']

    # Extract auth code from redirect
    auth_code = re.search(r'code=([^&]+)', redirect).group(1)
    print(f"  Auth code: {auth_code[:30]}...")

    print(f"[Step 4] Exchanging code for access token...")
    return auth_code, code_verifier


def get_access_token(auth_code, code_verifier):
    resp = requests.post(
        LOGIN_PROVIDER + "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": auth_code,
            "code_verifier": code_verifier,
        }
    )
    if resp.status_code != 200:
        print(f"  ERROR: {resp.text}")
        raise Exception(f"Token exchange failed: {resp.status_code}")

    token = resp.json()['access_token']
    print(f"  Token obtained: {token[:50]}...")
    return token


if __name__ == "__main__":
    print("Starting Panasonic OAuth authentication flow...\n")
    auth_code, code_verifier = get_authorization_code()
    access_token = get_access_token(auth_code, code_verifier)
    print(f"\n✓ Authentication successful!")
    print(f"Access Token: {access_token}")
