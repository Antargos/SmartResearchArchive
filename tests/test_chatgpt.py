"""Offline contract tests: no login, plan usage or external document submission."""

import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from src.chatgpt_auth import (AUTH, PLAN_SCOPE, ConnectionError, b64, callback_result,
                              connect, load, protect, save, session_lock, sign_in,
                              sign_out, validate_identity)
from src.chatgpt_client import ChatGPTClient, completed_text
from src.chatgpt_workflow import run_chatgpt
from src.main import review
from src.semantic import (analyze_document, approve_semantic_topics, chunks,
                          classify_semantically, parse_topics, propose_topics)
from test_archive import make_pdf


def event(kind, **fields):
    return ('data: ' + json.dumps(dict(type=kind, **fields)) + '\n\n').encode()


class FakeClient:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def json_result(self, instructions, content):
        self.calls.append((instructions, json.loads(content)))
        return next(self.results)


class AuthTests(unittest.TestCase):
    def test_browser_sign_in_contract_without_network_or_browser(self):
        captured = {}
        class Server:
            server_port = 54321
            def __init__(self, address, handler):
                self.handler = handler
                self.address = address
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def handle_request(self):
                query = captured['query']
                handler = object.__new__(self.handler)
                handler.path = '/auth/callback?' + urlencode(dict(
                    state=query['state'][0], code='synthetic-code', client_id='issued'))
                handler.send_response = lambda _: None
                handler.send_header = lambda *args: None
                handler.end_headers = lambda: None
                handler.wfile = io.BytesIO()
                handler.do_GET()
        def browser(url):
            captured['query'] = parse_qs(urlparse(url).query)
            return True
        def network(url, data=None, **kwargs):
            if '.well-known' in url:
                return {'issuer': AUTH, 'jwks_uri': AUTH + '/jwks'}
            captured['exchange'] = data
            return dict(id_token='synthetic-id', access_token='synthetic-access',
                        refresh_token='synthetic-refresh', scope=PLAN_SCOPE, expires_in=3600)
        state = {'host_id': 'urn:uuid:synthetic', 'profiles': [], 'active': None}
        with patch('src.chatgpt_auth.HTTPServer', Server), \
                patch('src.chatgpt_auth.webbrowser.open', side_effect=browser), \
                patch('src.chatgpt_auth.request', side_effect=network), \
                patch('src.chatgpt_auth.validate_identity', return_value={'sub': 'verified'}), \
                patch('src.chatgpt_auth.save'):
            profile = sign_in(state, ask=lambda _: '', show=lambda _: None)
        query, exchange = captured['query'], captured['exchange']
        self.assertEqual(query['client_id'], ['dynamic_agent_client'])
        self.assertEqual(query['agent_name_hint'], ['Smart Research Archive'])
        self.assertIn(PLAN_SCOPE, query['scope'][0])
        self.assertEqual(exchange['client_id'], 'issued')
        self.assertEqual(exchange['redirect_uri'], query['redirect_uri'][0])
        import hashlib
        self.assertEqual(query['code_challenge'][0], b64(hashlib.sha256(exchange['code_verifier'].encode()).digest()))
        self.assertEqual(profile['subject'], 'verified')

    def test_callback_state_client_and_declined_permission(self):
        self.assertEqual(callback_result('state=s&code=c&client_id=issued', 's'), ('c', 'issued'))
        self.assertEqual(callback_result('state=s&code=c', 's', 'issued'), ('c', 'issued'))
        for query in ('state=wrong&code=c&client_id=issued', 'state=s&error=access_denied',
                      'state=s&code=c', 'state=s&code=c&client_id=dynamic_agent_client',
                      'state=s&state=s&code=c&client_id=issued'):
            with self.subTest(query=query), self.assertRaises(ConnectionError):
                callback_result(query, 's')
        with self.assertRaises(ConnectionError):
            callback_result('state=s&code=c&client_id=other', 's', 'issued')

    def test_signed_identity_and_claim_rejections(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = key.public_key().public_numbers()
        encode_number = lambda value: b64(value.to_bytes((value.bit_length() + 7) // 8, 'big'))
        jwks = {'keys': [dict(kid='test', kty='RSA', e=encode_number(numbers.e), n=encode_number(numbers.n))]}
        config = {'issuer': AUTH, 'jwks_uri': AUTH + '/jwks'}
        claims = dict(iss=AUTH, aud='issued', sub='test-user', nonce='nonce', exp=2000, iat=900)
        def token(values, algorithm='RS256'):
            head = b64(json.dumps(dict(alg=algorithm, kid='test')).encode())
            body = b64(json.dumps(values).encode())
            signature = key.sign(f'{head}.{body}'.encode(), padding.PKCS1v15(), hashes.SHA256())
            return f'{head}.{body}.{b64(signature)}'
        with patch('src.chatgpt_auth.request', return_value=jwks):
            self.assertEqual(validate_identity(token(claims), 'issued', 'nonce', config, 1000)['sub'], 'test-user')
            for changes in ({'iss': 'https://evil.example'}, {'aud': 'other'}, {'nonce': 'wrong'},
                            {'exp': 900}, {'sub': ''}, {'nbf': 2000}):
                with self.subTest(changes=changes), self.assertRaises(ConnectionError):
                    validate_identity(token(dict(claims, **changes)), 'issued', 'nonce', config, 1000)
            with self.assertRaises(ConnectionError):
                validate_identity(token(claims, 'none'), 'issued', 'nonce', config, 1000)
            tampered = token(claims).split('.')
            tampered[1] = b64(json.dumps(dict(claims, sub='attacker')).encode())
            with self.assertRaises(ConnectionError):
                validate_identity('.'.join(tampered), 'issued', 'nonce', config, 1000)

    def test_protected_store_and_serialized_session(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            state = load(folder)
            state['profiles'].append({'access_token': 'synthetic-secret'})
            save(state, folder)
            self.assertEqual(load(folder), state)
            import os
            if os.name == 'nt':
                self.assertNotIn(b'synthetic-secret', (folder / 'session.dat').read_bytes())
            with session_lock(folder):
                with self.assertRaises(ConnectionError):
                    with session_lock(folder):
                        pass
            self.assertFalse((folder / 'runtime.lock').exists())

    def test_refresh_and_missing_plan_permission(self):
        profile = dict(client_id='issued', email='test@example.invalid', subject='test',
                       access_token='old', refresh_token='old-refresh', scopes=[PLAN_SCOPE], expires_at=0)
        state = {'profiles': [profile]}
        with patch('src.chatgpt_auth.select_profile', return_value=profile), \
                patch('src.chatgpt_auth.save'), \
                patch('src.chatgpt_auth.request', return_value=dict(access_token='new', refresh_token='new-refresh',
                                                                  expires_in=3600)) as request:
            self.assertEqual(connect(state)['access_token'], 'new')
            self.assertEqual(profile['refresh_token'], 'new-refresh')
            self.assertNotIn('scope', request.call_args.args[1])
            profile['scopes'] = []
            with self.assertRaises(ConnectionError):
                connect(state)

    def test_logout_clears_tokens_even_if_revocation_fails(self):
        profile = dict(client_id='issued', subject='test', access_token='a', refresh_token='r', id_token='i')
        state = {'profiles': [profile]}
        with patch('src.chatgpt_auth.select_profile', return_value=profile), \
                patch('src.chatgpt_auth.request', side_effect=ConnectionError('offline')), \
                patch('src.chatgpt_auth.save'), patch('builtins.print') as show:
            sign_out(state)
        self.assertNotIn('refresh_token', profile)
        self.assertEqual(profile['client_id'], 'issued')
        self.assertIn('not confirmed', show.call_args.args[0])


class ClientTests(unittest.TestCase):
    def test_completed_stream_and_partial_failures(self):
        data = event('response.output_text.delta', delta='hello') + event('response.completed')
        self.assertEqual(completed_text(io.BytesIO(data)), 'hello')
        for ending in (b'', event('response.failed'), event('response.incomplete'), event('error')):
            with self.subTest(ending=ending), self.assertRaises(ConnectionError):
                completed_text(io.BytesIO(event('response.output_text.delta', delta='partial') + ending))

    def test_public_api_contract_and_model_discovery(self):
        profile = {'access_token': 'synthetic'}
        with patch('src.chatgpt_client.request', return_value={
                'models': [dict(slug='available', display_name='Available', visibility='list')]}):
            self.assertEqual(ChatGPTClient.choose_model(profile, requested='available'), 'available')
            with self.assertRaises(ConnectionError):
                ChatGPTClient.choose_model(profile, requested='unknown')
        response = io.BytesIO(event('response.output_text.delta', delta='{"ok":true}') +
                              event('response.completed'))
        with patch('src.chatgpt_client.request', return_value=response) as request:
            self.assertEqual(ChatGPTClient(profile, 'available').json_result('rules', 'text'), {'ok': True})
            url, body = request.call_args.args
            self.assertEqual(url, 'https://api.openai.com/v1/responses')
            self.assertEqual(set(body), {'model', 'instructions', 'input', 'store', 'stream'})
            self.assertFalse(body['store'])
            self.assertTrue(body['stream'])
            self.assertIsInstance(body['input'], list)


class SemanticTests(unittest.TestCase):
    def test_chunk_coverage_and_verified_quotes(self):
        self.assertEqual(''.join(chunks('abcdefgh', 3)), 'abcdefgh')
        with self.assertRaises(ConnectionError):
            chunks('x' * 240001)
        fake = FakeClient([dict(summary='Historical migration.', evidence=['migration'])])
        result = analyze_document(fake, 'A study of migration.')
        self.assertEqual(result['evidence'], ['migration'])
        with self.assertRaises(ConnectionError):
            analyze_document(FakeClient([dict(summary='Summary', evidence=['invented quote'])]), 'migration')
        self.assertIsNone(analyze_document(FakeClient([]), ''))

    def test_safe_topics_and_unknown_evidence_rejected(self):
        candidate = dict(name='Migration', description='Migration history', documents=['PDF1'])
        self.assertEqual(parse_topics({'topics': [candidate]}, {'PDF1'})[0]['name'], 'Migration')
        for changes in ({'name': '../escape'}, {'name': 'CON'}, {'name': 'Unclassified'},
                        {'documents': ['unknown']}):
            with self.subTest(changes=changes), self.assertRaises(ConnectionError):
                parse_topics({'topics': [dict(candidate, **changes)]}, {'PDF1'})
        answers = iter(['c', 'Social History', 'Population movements', 'a'])
        topics = approve_semantic_topics([candidate], {'PDF1': 'a.pdf'},
                                         ask=lambda _: next(answers), show=lambda _: None)
        self.assertEqual(topics, {'Social History': 'Population movements'})

    def test_semantic_classification_and_abstention(self):
        analysis = {'summary': 'Wage disputes and collective action', 'evidence': ['wages']}
        result = classify_semantically(FakeClient([dict(topic='Labor History', reason='Collective action.')]),
                                       analysis, {'Labor History': 'History of workers and unions'})
        self.assertEqual(result[0], 'Labor History')
        self.assertEqual(classify_semantically(FakeClient([]), None, {})[0], 'Unclassified')
        with self.assertRaises(ConnectionError):
            classify_semantically(FakeClient([dict(topic='unknown', reason='Invalid')]), analysis,
                                  {'Labor History': 'Workers'})

    def test_external_consent_and_full_review_with_mocked_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'paper.pdf'
            make_pdf(source)
            with patch('src.chatgpt_workflow.connect') as connect:
                run_chatgpt([source], root / 'out', review, ask=lambda _: 'n', show=lambda _: None)
                connect.assert_not_called()
            fake = FakeClient([dict(summary='Digital historical methods', evidence=['Digital history']),
                               {'topics': [dict(name='Historical Methods', description='Digital approaches',
                                               documents=['PDF1'])]},
                               dict(topic='Historical Methods', reason='Discusses digital methods')])
            answers = iter(['y', 'a', 'a'])
            with patch('src.chatgpt_workflow.session_lock'), patch('src.chatgpt_workflow.load'), \
                    patch('src.chatgpt_workflow.connect', return_value={}), \
                    patch('src.chatgpt_workflow.ChatGPTClient') as provider:
                provider.choose_model.return_value = 'mock-model'
                provider.return_value = fake
                run_chatgpt([source], root / 'out', review, ask=lambda _: next(answers), show=lambda _: None)
            self.assertFalse(source.exists())
            self.assertTrue((root / 'out' / 'Historical Methods' / 'Test_Author_2024_A_Test_Paper.pdf').exists())

    def test_semantic_preview_does_not_move_pdfs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'paper.pdf'
            make_pdf(source)
            fake = FakeClient([dict(summary='Historical methods', evidence=['Digital history']),
                               {'topics': [dict(name='Methods', description='Historical methods', documents=['PDF1'])]}])
            answers = iter(['y', 'a'])
            with patch('src.chatgpt_workflow.session_lock'), patch('src.chatgpt_workflow.load'), \
                    patch('src.chatgpt_workflow.connect', return_value={}), \
                    patch('src.chatgpt_workflow.ChatGPTClient') as provider:
                provider.choose_model.return_value = 'mock-model'
                provider.return_value = fake
                run_chatgpt([source], root / 'out', review, topics_only=True,
                            ask=lambda _: next(answers), show=lambda _: None)
            self.assertTrue(source.exists())
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
