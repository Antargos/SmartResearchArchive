"""Connection deletion uses synthetic records, never real account credentials."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from src.chatgpt_auth import AUTH, ConnectionError, delete_profile


class ConnectionDeletionTests(unittest.TestCase):
    def state(self):
        return {'host_id': 'urn:uuid:keep-this-host', 'active': 'first', 'profiles': [
            {'client_id': 'first', 'email': 'same@example.invalid', 'subject': 'user',
             'access_token': 'synthetic-a', 'refresh_token': 'synthetic-r', 'id_token': 'synthetic-i'},
            {'client_id': 'second', 'email': 'same@example.invalid', 'subject': 'user',
             'access_token': 'other-a', 'refresh_token': 'other-r'}]}

    def test_revoke_then_delete_one_registration_and_preserve_same_email_account(self):
        state = self.state()
        other = deepcopy(state['profiles'][1])
        def network(url, data=None, **kwargs):
            # No state is deleted until after the revoke attempt.
            self.assertEqual(len(state['profiles']), 2)
            if data is None:
                return {'revocation_endpoint': AUTH + '/revoke'}
            self.assertEqual(url, AUTH + '/revoke')
            self.assertEqual(data, {'token': 'synthetic-r', 'token_type_hint': 'refresh_token', 'client_id': 'first'})
            return {}
        with patch('src.chatgpt_auth.request', side_effect=network), patch('src.chatgpt_auth.save') as save:
            self.assertIs(delete_profile(state, 'first'), True)
        self.assertEqual(state['profiles'], [other])
        self.assertIsNone(state['active'])
        self.assertEqual(state['host_id'], 'urn:uuid:keep-this-host')
        self.assertEqual(save.call_args.args[0]['profiles'], [other])

    def test_network_failure_still_deletes_locally_and_reports_unconfirmed(self):
        state = self.state()
        with patch('src.chatgpt_auth.request', side_effect=ConnectionError('offline')), \
                patch('src.chatgpt_auth.save'):
            self.assertIs(delete_profile(state, 'second'), False)
        self.assertEqual([p['client_id'] for p in state['profiles']], ['first'])
        self.assertEqual(state['active'], 'first')

    def test_signed_out_or_pending_record_can_be_deleted_without_network(self):
        state = {'host_id': 'stable', 'active': 'pending', 'profiles': [{'client_id': 'pending', 'subject': None}]}
        with patch('src.chatgpt_auth.request') as request, patch('src.chatgpt_auth.save'):
            self.assertIsNone(delete_profile(state, 'pending'))
            request.assert_not_called()
        self.assertEqual(state['profiles'], [])
        self.assertIsNone(state['active'])
        self.assertEqual(state['host_id'], 'stable')

    def test_unknown_profile_does_not_touch_anything(self):
        state = self.state()
        before = deepcopy(state)
        with patch('src.chatgpt_auth.request') as request, patch('src.chatgpt_auth.save') as save:
            with self.assertRaises(ValueError):
                delete_profile(state, 'missing')
            request.assert_not_called()
            save.assert_not_called()
        self.assertEqual(state, before)

    def test_failed_disk_write_keeps_in_memory_record(self):
        state = self.state()
        before = deepcopy(state)
        with patch('src.chatgpt_auth.revoke_session', return_value=True), \
                patch('src.chatgpt_auth.save', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                delete_profile(state, 'first')
        self.assertEqual(state, before)

    def test_untrusted_revocation_endpoint_is_never_sent_a_token(self):
        state = self.state()
        with patch('src.chatgpt_auth.request', return_value={'revocation_endpoint': 'https://invalid.example/revoke'}) as request, \
                patch('src.chatgpt_auth.save'):
            self.assertIs(delete_profile(state, 'first'), False)
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
