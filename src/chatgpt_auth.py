"""Documented Sign in with ChatGPT flow. Never reuse Codex/browser credentials."""

import base64
from contextlib import contextmanager
import ctypes
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid
import webbrowser

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

AUTH = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
PLAN_SCOPE = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + PLAN_SCOPE
STORE = Path('.chatgpt')


class ConnectionError(RuntimeError):
    """A safe, user-facing error that does not include tokens or server bodies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Do not forward credentials to a redirect target.


def request(url, data=None, token=None, form=False, stream=False):
    headers = {'Accept': 'text/event-stream' if stream else 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = None
    if data is not None:
        body = urlencode(data).encode() if form else json.dumps(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    try:
        response = build_opener(NoRedirect()).open(Request(url, body, headers), timeout=120)
        if stream:
            return response
        with response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        raise ConnectionError(f'OpenAI request failed (HTTP {error.code}). '
                              'Check sign-in, plan access and usage limits in ChatGPT settings.') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ConnectionError('OpenAI connection failed or returned invalid data; no result accepted.') from None


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def validate_identity(token, client_id, nonce, config, now=None):
    """Verify RS256 signature and OIDC claims; never merely decode a JWT."""
    try:
        header_text, payload_text, signature = token.split('.')
        header = json.loads(unb64(header_text))
        claims = json.loads(unb64(payload_text))
        if header.get('alg') != 'RS256' or not header.get('kid'):
            raise ValueError('algorithm')
        jwks_url = config['jwks_uri']
        if urlparse(jwks_url).scheme != 'https' or urlparse(jwks_url).netloc != 'auth.openai.com':
            raise ValueError('JWKS host')
        keys = request(jwks_url)['keys']
        key = next(k for k in keys if k.get('kid') == header.get('kid') and k.get('kty') == 'RSA')
        public = rsa.RSAPublicNumbers(int.from_bytes(unb64(key['e']), 'big'),
                                     int.from_bytes(unb64(key['n']), 'big')).public_key()
        public.verify(unb64(signature), f'{header_text}.{payload_text}'.encode(),
                      padding.PKCS1v15(), hashes.SHA256())
        now = time.time() if now is None else now
        audience = claims.get('aud')
        if (claims.get('iss') != AUTH or config.get('issuer') != AUTH
                or client_id not in (audience if isinstance(audience, list) else [audience])
                or not isinstance(claims.get('exp'), (int, float)) or claims['exp'] <= now
                or claims.get('nbf', 0) > now + 30 or claims.get('iat', 0) > now + 30
                or not isinstance(claims.get('nonce'), str)
                or not secrets.compare_digest(claims['nonce'], nonce)
                or not isinstance(claims.get('sub'), str) or not claims['sub']):
            raise ValueError('claims')
        if isinstance(audience, list) and len(audience) > 1 and claims.get('azp') != client_id:
            raise ValueError('authorized party')
        return claims
    except ConnectionError:
        raise
    except Exception:
        raise ConnectionError('ChatGPT identity validation failed; credentials were not saved.') from None


def protect(data, decrypt=False):
    """Windows DPAPI protects secrets for the current OS user. POSIX uses mode 600."""
    if os.name != 'nt':
        return data
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ConnectionError('Could not protect/read local credentials for this Windows user.')
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


def save(state, folder=STORE):
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = folder / 'session.tmp'
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    with os.fdopen(os.open(temporary, flags, 0o600), 'wb') as file:
        file.write(protect(json.dumps(state).encode()))
    temporary.replace(folder / 'session.dat')


def load(folder=STORE):
    path = folder / 'session.dat'
    if not path.exists():
        return {'host_id': 'urn:uuid:' + str(uuid.uuid4()), 'profiles': [], 'active': None}
    if os.name != 'nt' and path.stat().st_mode & 0o077:
        raise ConnectionError('Credential file permissions must be 600.')
    try:
        return json.loads(protect(path.read_bytes(), decrypt=True))
    except ConnectionError:
        raise
    except Exception:
        raise ConnectionError('Cannot read local ChatGPT session. Do not share session.dat.') from None


@contextmanager
def session_lock(folder=STORE):
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = folder / 'runtime.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise ConnectionError('Another ChatGPT run is active. If it crashed, remove .chatgpt/runtime.lock.') from None
    try:
        yield
    finally:
        lock.rmdir()


def callback_result(query, state, existing=None):
    values = parse_qs(query, keep_blank_values=True)
    def one(key):
        items = values.get(key, [])
        return items[0] if len(items) == 1 else ''
    if not secrets.compare_digest(one('state'), state):
        raise ConnectionError('Invalid sign-in state.')
    if one('error'):
        raise ConnectionError('ChatGPT authorization was declined or unavailable.')
    client = one('client_id') or existing
    if (not client or client == 'dynamic_agent_client' or not one('code')
            or (existing and client != existing)):
        raise ConnectionError('Incomplete or mismatched ChatGPT client registration.')
    return one('code'), client


def sign_in(state, previous=None, ask=input, show=print):
    save(state)  # Persist this installation's host ID even if sign-in is cancelled.
    config = request(AUTH + '/.well-known/openid-configuration')
    verifier, nonce, expected = secrets.token_urlsafe(48), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Callback URLs contain an authorization code; do not log them.

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != '/auth/callback':
                self.send_error(404)
                return
            try:
                result['value'] = callback_result(parsed.query, expected,
                                                previous['client_id'] if previous else None)
            except ConnectionError as error:
                # A forged state must not terminate the legitimate pending attempt.
                self.send_error(400, 'Invalid authorization callback')
                if parse_qs(parsed.query).get('state') == [expected]:
                    result['error'] = error
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'Returned to Smart Research Archive. You can close this tab.')

    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}/auth/callback'
        parameters = dict(client_id=previous['client_id'] if previous else 'dynamic_agent_client',
                          ext_agent_host_id=state['host_id'], response_type='code',
                          redirect_uri=redirect, scope=SCOPES, resource=RESOURCE,
                          state=expected, nonce=nonce, code_challenge_method='S256',
                          code_challenge=b64(hashlib.sha256(verifier.encode()).digest()))
        if previous:
            if previous.get('id_token'):
                parameters['id_token_hint'] = previous['id_token']
        else:
            parameters['agent_name_hint'] = 'Smart Research Archive'
        show('Continue with ChatGPT — sign in and allow ChatGPT plan usage in your browser.')
        ask('Press Enter to open the sign-in page (Ctrl+C cancels): ')
        url = AUTH + '/api/accounts/authorize?' + urlencode(parameters)
        if not webbrowser.open(url):
            raise ConnectionError('Could not open the browser. Check your default browser and try again.')
        deadline = time.monotonic() + 300
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if not result:
        raise ConnectionError('Sign-in timed out. Run sign-in again.')
    if 'error' in result:
        raise result['error']
    code, client = result['value']
    if previous is None:
        # Keep an issued registration after a failed/expired code exchange so the
        # next attempt can reuse it. This pending profile has no verified identity.
        previous = dict(client_id=client, subject=None, email='Pending connection')
        state['profiles'].append(previous)
        save(state)
    tokens = request(AUTH + '/api/accounts/oauth/token',
                     dict(grant_type='authorization_code', client_id=client, code=code,
                          code_verifier=verifier, redirect_uri=redirect, resource=RESOURCE), form=True)
    claims = validate_identity(tokens.get('id_token', ''), client, nonce, config)
    if previous and previous.get('subject') and claims['sub'] != previous['subject']:
        raise ConnectionError('The signed-in identity differs from the selected profile.')
    profile = dict(tokens, client_id=client, subject=claims['sub'],
                   email=claims.get('email', 'ChatGPT account'),
                   scopes=tokens.get('scope', '').split(),
                   expires_at=time.time() + float(tokens.get('expires_in', 0)))
    if previous:
        state['profiles'][state['profiles'].index(previous)] = profile
    else:
        state['profiles'].append(profile)
    state['active'] = client
    save(state)
    return profile


def select_profile(state, ask=input, show=print):
    if not state['profiles']:
        return None
    for index, profile in enumerate(state['profiles'], 1):
        show(f'{index}. {profile["email"]} (connection {index})')
    while True:
        choice = ask('Account number, or 0 to connect another account/workspace: ').strip()
        if choice.isdigit() and 0 <= int(choice) <= len(state['profiles']):
            return state['profiles'][int(choice) - 1] if int(choice) else None
        show('Choose one of the displayed numbers.')


def connect(state, login=False):
    profile = select_profile(state)
    if profile is None or login or not profile.get('access_token'):
        profile = sign_in(state, profile)
    state['active'] = profile['client_id']
    if PLAN_SCOPE not in profile.get('scopes', []):
        raise ConnectionError('Signed in, but ChatGPT plan usage is not enabled. Sign in again and authorize it.')
    refresh(state, profile)
    print(f'Using ChatGPT plan: {profile["email"]}. Manage usage in ChatGPT Settings > Usage.')
    return profile


def refresh(state, profile):
    """Called before each request; the enclosing session lock serializes rotation."""
    if profile.get('expires_at', 0) <= time.time() + 60:
        if not profile.get('refresh_token'):
            raise ConnectionError('Session expired. Run --chatgpt-login again.')
        tokens = request(AUTH + '/api/accounts/oauth/token',
                         dict(grant_type='refresh_token', client_id=profile['client_id'],
                              refresh_token=profile['refresh_token'], resource=RESOURCE), form=True)
        # Keep the originally validated ID token as a login hint; no unvalidated identity replacement.
        for key in ('access_token', 'refresh_token', 'token_type'):
            if key in tokens:
                profile[key] = tokens[key]
        if 'scope' in tokens:
            profile['scopes'] = tokens['scope'].split()
        profile['expires_at'] = time.time() + float(tokens.get('expires_in', 0))
    save(state)
    if PLAN_SCOPE not in profile.get('scopes', []) or not profile.get('access_token'):
        raise ConnectionError('ChatGPT plan usage permission is missing.')


def sign_out(state):
    profile = select_profile(state)
    if profile is None:
        return
    confirmed = False
    try:
        endpoint = request(AUTH + '/.well-known/openid-configuration')['revocation_endpoint']
        if urlparse(endpoint).scheme != 'https' or urlparse(endpoint).netloc != 'auth.openai.com':
            raise ConnectionError('Unexpected revocation endpoint.')
        if profile.get('refresh_token'):
            request(endpoint, dict(token=profile['refresh_token'], token_type_hint='refresh_token',
                                   client_id=profile['client_id']), form=True)
            confirmed = True
    except (ConnectionError, KeyError):
        pass
    for key in ('access_token', 'refresh_token', 'id_token', 'expires_at', 'scope', 'scopes'):
        profile.pop(key, None)
    save(state)
    print('Signed out locally. ' + ('Renewable session revoked.' if confirmed else
          'Remote revocation was not confirmed; disconnect the app in ChatGPT Settings.'))
