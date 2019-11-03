import functools
import json

from redis import StrictRedis
from redis.exceptions import ConnectionError as RedisConnectionException


def cached(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if cache.is_connected:
            key = str(func.__name__)
            if args:
                args_str = '_'.join('%s' % arg for arg in args)
                key += '_' + args_str
            if kwargs:
                kwarg_str = '_'.join(
                    '%s=%s' % (key, value) for key, value in kwargs.items()
                )
                key += '_' + kwarg_str

            result = cache.get(key)

            if result is None:
                result = func(*args, **kwargs)
                cache.set(key, result)
        else:
            result = func(*args, **kwargs)

        return result

    return wrapper


class RedisCache:
    def __init__(self):
        self.cache_obj = StrictRedis()
        self.is_connected = None

    def _perform_operation(self, op_name, *args, **kwargs):
        if op_name != 'ping' and not self.is_connected:
            return None
        op_dict = {
            'ping': self.cache_obj.ping,
            'get': self.cache_obj.get,
            'set': self.cache_obj.set,
        }
        try:
            result = op_dict[op_name](*args, **kwargs)
        except RedisConnectionException:
            print('Failed to connect to Redis Server')
            return None
        except Exception as e:
            print(e)
            return None
        else:
            return result

    def connect(self):
        self.is_connected = self._perform_operation('ping')

    def get(self, key):
        value = self._perform_operation('get', key)

        if value:
            value_json = value.decode('utf-8')
            value = json.loads(value_json)
        return value

    def set(self, key, value, ttl=86400):
        value_json = json.dumps(value)
        return self._perform_operation('set', key, value_json, ttl)


cache = RedisCache()
cache.connect()  # How do i prevent from connecting during test?
