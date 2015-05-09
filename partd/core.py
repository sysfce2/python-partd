from __future__ import absolute_import

import os
import shutil
import locket
import string
from toolz import memoize
from contextlib import contextmanager


locks = dict()


def lock(path):
    if path not in locks:
        locks[path] = locket.lock_file(os.path.join(path, '.lock'))
    return locks[path]


# http://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename-in-python
valid_chars = "-_.() " + string.ascii_letters + string.digits + os.path.sep


def escape_filename(fn):
    """ Escape text so that it is a valid filename

    >>> escape_filename('Foo!bar?')
    'Foobar'

    """
    return ''.join(filter(valid_chars.__contains__, fn))


def filename(path, key):
    return os.path.join(path, escape_filename(token(key)))


def token(key):
    """

    >>> token('hello')
    'hello'
    >>> token(('hello', 'world'))  # doctest: +SKIP
    'hello/world'
    """
    if isinstance(key, str):
        return key
    elif isinstance(key, tuple):
        return os.path.join(*map(token, key))
    else:
        return str(key)


def create(path):
    os.mkdir(path)
    with lock(path): pass


def put(path, data, lock=lock):
    if not lock:
        lock = do_nothing
    with lock(path):
        for k, v in data.items():
            fn = filename(path, k)
            if not os.path.exists(os.path.dirname(fn)):
                os.makedirs(os.path.dirname(fn))
            with open(fn, 'ab') as f:
                f.write(v)


def get(path, keys, lock=lock):
    assert isinstance(keys, (list, tuple, set))
    if not lock:
        lock = do_nothing
    with lock(path):
        result = []
        for key in keys:
            try:
                with open(filename(path, key), 'rb') as f:
                    result.append(f.read())
            except IOError:
                result.append(b'')
    return result


def destroy(path):
    shutil.rmtree(path)
    old_keys = set([key for key in _ensured if key[0] == path])
    for key in old_keys:
        _ensured.remove(key)


_ensured = set()

def ensure(path, key, data, put=put):
    """ Write once key-value assignment.  Use for metadata storage.

    You may write a key once.  You may not append.
    Subsequent writes of the same key-value pair are very cheap

    >>> ensure('path', 'x', b'123')  # doctest: +SKIP
    >>> ensure('path', 'x', b'123')  # doctest: +SKIP

    Safe to get without lock

    >>> get('path', ['x'], lock=False)  # doctest: +SKIP
    b'123'
    """
    if (path, key) in _ensured:
        return
    else:
        _ensured.add((path, key))
        put(path, {key: data}, lock=False)


def exists(path, key):
    """ Key exists in path """
    return os.path.exists(filename(path, key))


@contextmanager
def do_nothing(*args, **kwargs):
    yield


@contextmanager
def partd(path='tmp.partd', create=create, destroy=destroy, **kwargs):
    if os.path.exists(path):
        shutil.rmtree(path)

    create(path, **kwargs)

    try:
        yield path
    finally:
        destroy(path)
