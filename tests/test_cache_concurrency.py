import unittest
import tempfile
import os
import time
import threading
from unittest.mock import patch, Mock
import sqlite3

from storage.cache import Cache, rate_limited_get


class TestCacheTTLAndConcurrency(unittest.TestCase):
    def test_ttl_eviction_refreshes_entry(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = tmp.name
        tmp.close()
        try:
            cache = Cache(path)
            # seed cache with an old response
            mock_old = Mock()
            mock_old.status_code = 200
            mock_old.json.return_value = {'v': 1}
            with patch('storage.cache.requests.get', return_value=mock_old):
                _ = rate_limited_get('http://example.com/ttl', cache=cache, cache_key='ttl_k', min_wait=0)

            # age the entry to be older than max_age
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            old_ts = time.time() - 3600  # 1 hour ago
            cur.execute('UPDATE http_cache SET timestamp = ? WHERE key = ?', (old_ts, 'ttl_k'))
            conn.commit()
            conn.close()

            # now patch requests.get to return a new value and ensure it is used when max_age is small
            mock_new = Mock()
            mock_new.status_code = 200
            mock_new.json.return_value = {'v': 2}
            with patch('storage.cache.requests.get', return_value=mock_new) as mocked_get:
                res = rate_limited_get('http://example.com/ttl', cache=cache, cache_key='ttl_k', min_wait=0, max_age=5)
                self.assertEqual(res['response'], {'v': 2})
                self.assertTrue(mocked_get.called)

            # a subsequent call with large max_age should hit cache and not call requests.get
            with patch('storage.cache.requests.get', side_effect=AssertionError('should not be called')):
                res2 = rate_limited_get('http://example.com/ttl', cache=cache, cache_key='ttl_k', min_wait=0, max_age=3600)
                self.assertEqual(res2['response'], {'v': 2})

        finally:
            try:
                cache.close()
            except Exception:
                pass
            try:
                os.remove(path)
            except Exception:
                pass

    def test_concurrent_set_get_no_corruption(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = tmp.name
        tmp.close()
        try:
            cache = Cache(path)
            num_threads = 8
            keys_per_thread = 100
            errors = []

            def worker(thread_idx):
                try:
                    for i in range(keys_per_thread):
                        key = f"t{thread_idx}_k{i}"
                        cache.set(key, {'thread': thread_idx, 'i': i}, status=200)
                        entry = cache.get(key)
                        if entry is None or entry.get('response', {}).get('i') != i:
                            errors.append((thread_idx, i))
                except Exception as ex:
                    errors.append(('exc', thread_idx, str(ex)))

            threads = [threading.Thread(target=worker, args=(ti,)) for ti in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # verify no errors occurred and all keys are present
            self.assertEqual(len(errors), 0, f"Errors occurred in threads: {errors}")
            # verify a sample of keys exist
            found = 0
            for ti in range(num_threads):
                for i in range(0, keys_per_thread, 10):  # spot-check every 10th key
                    key = f"t{ti}_k{i}"
                    entry = cache.get(key)
                    if entry:
                        found += 1
            self.assertGreater(found, 0)

        finally:
            try:
                cache.close()
            except Exception:
                pass
            try:
                os.remove(path)
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
