import functools
import json
import logging

from redis import StrictRedis
from redis.exceptions import ConnectionError as RedisConnectionException

logger = logging.getLogger(__name__)


def cached(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not cache.initialized:
            cache.connect()

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
        self.cache_obj = None
        self.initialized = False
        self.is_connected = False

    def _perform_operation(self, op_name, *args, **kwargs):
        if self.initialized and not self.is_connected:
            return None
        op_dict = {
            'ping': self.cache_obj.ping,
            'get': self.cache_obj.get,
            'set': self.cache_obj.set,
        }
        try:
            result = op_dict[op_name](*args, **kwargs)
        except RedisConnectionException:
            logger.warning('Failed to connect to Redis Server')
            return None
        except Exception as e:
            logger.exception(e)
            return None
        else:
            return result

    def connect(self, host, port):
        self.cache_obj = StrictRedis(host=host, port=port)
        self.is_connected = self._perform_operation('ping')
        if self.is_connected:
            logger.info(
                'Successfully connected to the Redis Server on host: %s:%s', host, port
            )
        else:
            logger.warning(
                'Failed to connect to the Redis Server on host: %s:%s', host, port
            )
        self.initialized = True

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
