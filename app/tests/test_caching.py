import json
import unittest
from unittest import mock

from app.caching import cache, cached


@cached
def test_sum_two_args(arg1, arg2):
    return arg1 + arg2


class TestCacheWrapper(unittest.TestCase):
    @mock.patch('app.caching.cache', autospec=True)
    def test_decorator_not_connected(self, mock_cache_instance):
        mock_cache_instance.initialized = True
        mock_cache_instance.is_connected = False
        mock_cache_instance.get = mock.Mock()
        mock_cache_instance.set = mock.Mock()

        result = test_sum_two_args(1, 2)

        mock_cache_instance.get.assert_not_called()
        mock_cache_instance.set.assert_not_called()
        self.assertEqual(result, 3)

    @mock.patch('app.caching.cache', autospec=True)
    def test_decorator_not_cached_args(self, mock_cache_instance):
        mock_cache_instance.initialized = True
        mock_cache_instance.is_connected = True
        mock_cache_instance.get = mock.Mock(return_value=None)
        mock_cache_instance.set = mock.Mock()

        result = test_sum_two_args(1, 2)

        cache_key = 'test_sum_two_args_1_2'
        mock_cache_instance.get.assert_called_once_with(cache_key)
        mock_cache_instance.set.assert_called_once_with(cache_key, 3)
        self.assertEqual(result, 3)

    @mock.patch('app.caching.cache', autospec=True)
    def test_decorator_cached_args(self, mock_cache_instance):
        mock_cache_instance.initialized = True
        mock_cache_instance.is_connected = True
        mock_cache_instance.get = mock.Mock(return_value=3)
        mock_cache_instance.set = mock.Mock()

        result = test_sum_two_args(1, 2)

        cache_key = 'test_sum_two_args_1_2'
        mock_cache_instance.get.assert_called_once_with(cache_key)
        mock_cache_instance.set.assert_not_called()
        self.assertEqual(result, 3)

    def test_cache_get_not_connected(self):
        cache.initialized = True
        cache.is_connected = False
        result = cache.get('hello')
        self.assertEqual(result, None)

    @mock.patch('app.caching.cache.cache_obj')
    def test_cache_get_string(self, mock_cache):
        mock_cache.get.return_value = json.dumps('world').encode('utf-8')
        cache.initialized = True
        cache.is_connected = True
        result = cache.get('hello')

        mock_cache.get.assert_called_once_with('hello')
        self.assertEqual(result, 'world')

    @mock.patch('app.caching.cache.cache_obj')
    def test_cache_get_int(self, mock_cache):
        mock_cache.get.return_value = json.dumps(42).encode('utf-8')
        cache.initialized = True
        cache.is_connected = True
        result = cache.get('hello')
        self.assertEqual(result, 42)

    def test_cache_set_not_connected(self):
        cache.initialized = True
        cache.is_connected = False
        result = cache.set('hello', 'world')
        self.assertEqual(result, None)

    @mock.patch('app.caching.cache.cache_obj')
    def test_cache_set_string(self, mock_cache):
        mock_cache.set.return_value = True
        cache.initialized = True
        cache.is_connected = True
        result = cache.set('hello', 'world')
        mock_cache.set.assert_called_once_with('hello', json.dumps('world'), 86400)
        self.assertEqual(result, True)

    @mock.patch('app.caching.cache.cache_obj')
    def test_cache_set_float(self, mock_cache):
        mock_cache.set.return_value = True
        cache.initialized = True
        cache.is_connected = True
        result = cache.set('num', 99.32)
        mock_cache.set.assert_called_once_with('num', json.dumps(99.32), 86400)
        self.assertEqual(result, True)


if __name__ == '__main__':
    unittest.main()
