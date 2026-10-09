"""Extended attributes via Python's Linux API or the native macOS API."""

import ctypes
import errno
import os
import sys
from typing import Callable, Dict, List, cast


_libc = ctypes.CDLL(None, use_errno=True) if sys.platform == 'darwin' else None
if _libc is not None:
    _libc.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    _libc.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                             ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
    _libc.setxattr.argtypes = _libc.getxattr.argtypes
    _libc.removexattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    _libc.listxattr.restype = _libc.getxattr.restype = ctypes.c_ssize_t
    _libc.setxattr.restype = _libc.removexattr.restype = ctypes.c_int


def supported() -> bool:
    return _libc is not None or all(hasattr(os, name) for name in (
        'listxattr', 'getxattr', 'setxattr', 'removexattr',
    ))


def _checked(result: int, path: str) -> int:
    if result < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), path)
    return result


def _read_native(path: str, name: str = '') -> bytes:
    assert _libc is not None
    args = (os.fsencode(path), os.fsencode(name)) if name else (os.fsencode(path),)
    tail = (0, 0) if name else (0,)
    call = _libc.getxattr if name else _libc.listxattr
    size = _checked(call(*args, None, 0, *tail), path)
    if not size:
        return b''
    buffer = ctypes.create_string_buffer(size)
    length = _checked(call(*args, buffer, size, *tail), path)
    return buffer.raw[:length]


def read(path: str) -> Dict[str, bytes]:
    if not supported():
        return {}
    try:
        if _libc is not None:
            names = _read_native(path).split(b'\0')
            return {os.fsdecode(name): _read_native(path, os.fsdecode(name))
                    for name in names if name}
        list_attrs = cast(Callable[[str], List[str]], getattr(os, 'listxattr'))
        get_attr = cast(Callable[[str, str], bytes], getattr(os, 'getxattr'))
        return {name: get_attr(path, name) for name in list_attrs(path)}
    except OSError as exc:
        if exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP):
            return {}
        raise


def write(path: str, name: str, value: bytes) -> None:
    if _libc is not None:
        _checked(_libc.setxattr(os.fsencode(path), os.fsencode(name), value,
                               len(value), 0, 0), path)
    else:
        set_attr = cast(Callable[[str, str, bytes], None], getattr(os, 'setxattr'))
        set_attr(path, name, value)


def remove(path: str, name: str) -> None:
    if _libc is not None:
        _checked(_libc.removexattr(os.fsencode(path), os.fsencode(name), 0), path)
    else:
        remove_attr = cast(Callable[[str, str], None], getattr(os, 'removexattr'))
        remove_attr(path, name)
