import unittest
import tempfile
import os
import time
import sqlite3
from unittest.mock import patch, Mock

from storage.cache import Cache, rate_limited_get

class TestCacheBehavior(unittest.TestCase):
    def test_cache_set_get(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = tmp.name
        tmp.close()
        try:
            cache = Cache(path)
            cache.set('k1', {'a': 1}, status=200)
            entry = cache.get('k1')
            self.assertIsNotNone(entry)
            self.assertEqual(entry['response'], {'a': 1})
            self.assertEqual(entry['status'], 200)
            self.assertIn('timestamp', entry)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_rate_limited_get_caches_response(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = tmp.name
        tmp.close()
        try:
            cache = Cache(path)
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {'a': 1}

            with patch('storage.cache.requests.get', return_value=mock_resp):
                res1 = rate_limited_get('http://example.com', headers={}, params={}, cache=cache, cache_key='k2', min_wait=0)
                self.assertEqual(res1['response'], {'a': 1})
                self.assertEqual(res1['status'], 200)

            # Now ensure cached hit does not call requests.get by making requests.get raise if called
            def _fail(*args, **kwargs):
                raise AssertionError('requests.get should not be called on cached hit')

            with patch('storage.cache.requests.get', side_effect=_fail):
                res2 = rate_limited_get('http://example.com', headers={}, params={}, cache=cache, cache_key='k2', min_wait=0)
                self.assertEqual(res2['response'], {'a': 1})
                self.assertEqual(res2['status'], 200)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_rate_limited_get_respects_max_age(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = tmp.name
        tmp.close()
        try:
            cache = Cache(path)
            # seed the cache with an old entry
            mock_resp_old = Mock()
            mock_resp_old.status_code = 200
            mock_resp_old.json.return_value = {'a': 1}
            with patch('storage.cache.requests.get', return_value=mock_resp_old):
                _ = rate_limited_get('http://example.com', headers={}, params={}, cache=cache, cache_key='k3', min_wait=0)

            # manually age the cache entry so it's older than max_age
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            old_ts = time.time() - 3600  # 1 hour ago
            cur.execute('UPDATE http_cache SET timestamp = ? WHERE key = ?', (old_ts, 'k3'))
            conn.commit()
            conn.close()

            # now patch requests.get to return a fresh response
            mock_resp_new = Mock()
            mock_resp_new.status_code = 200
            mock_resp_new.json.return_value = {'a': 2}

            with patch('storage.cache.requests.get', return_value=mock_resp_new) as mocked_get:
                res = rate_limited_get('http://example.com', headers={}, params={}, cache=cache, cache_key='k3', min_wait=0, max_age=5)
                # since the cached entry is older than max_age, requests.get should have been called
                self.assertEqual(res['response'], {'a': 2})
                self.assertEqual(res['status'], 200)
                self.assertTrue(mocked_get.called)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

if __name__ == '__main__':
    unittest.main()

