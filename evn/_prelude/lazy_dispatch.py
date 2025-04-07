import re

# lazy_dispatch.py
import contextlib
import sys
from functools import wraps
from typing import Callable, Union, Dict, Optional

GLOBAL_DISPATCHERS: Dict[str, 'LazyDispatcher'] = {}


def _qualify(func: Callable, scope: Optional[str]) -> str:
    mod = func.__module__
    name = func.__name__
    qname = func.__qualname__

    if scope == 'local':
        return f'{mod}.{qname}'
    elif scope == 'global':
        return name
    elif scope == 'project':
        parts = mod.split('.')
        root = parts[0] if parts else mod
        return f'{root}.{name}'
    elif scope == 'subpackage':
        parts = mod.split('.')
        subpkg = '.'.join(parts[:-1])
        return f'{subpkg}.{name}'
    else:
        return f'{mod}.{qname}'  # default to local


class LazyDispatcher:

    def __init__(self, func: Callable, scope: Optional[str] = None):
        self._base_func = func
        self._registry = {}  # type: Dict[Union[str, type], Callable]
        self._resolved_types = {}
        self._key = _qualify(func, scope)
        wraps(func)(self)

        # GLOBAL_DISPATCHERS[self._key] = self

    def _register(self, typ: Union[str, type], func: Callable):
        self._registry[typ] = func
        return self

    def register(self, typ: Union[str, type]):

        def decorator(func):
            return self._register(typ, func)

        return decorator

    def _resolve_lazy_types(self):
        for typ in list(self._registry):
            if isinstance(typ, str) and typ not in self._resolved_types:
                if not is_valid_qualname(typ):
                    raise ValueError(f'Invalid type name: {typ}')
                modname, _, typename = typ.rpartition('.')
                # if not evn.installed[modname]:
                # raise TypeError(f"Module {modname} is not installed.")
                if mod := sys.modules.get(modname):
                    with contextlib.suppress(AttributeError):
                        self._resolved_types[typ] = getattr(mod, typename)
                        self._registry[
                            self._resolved_types[typ]] = self._registry[typ]

    def __call__(self, obj, *args, **kwargs):
        self._resolve_lazy_types()
        obj_type = type(obj)

        if obj_type in self._registry:
            # print('in registery')
            return self._registry[obj_type](obj, *args, **kwargs)

        # for key, func in self._registry.items():
        # if isinstance(key, str):
        # resolved = self._resolved_types.get(key)
        # if resolved and isinstance(obj, resolved):
        # return func(obj, *args, **kwargs)

        for key, func in self._registry.items():
            if isinstance(key, type) and isinstance(obj, key):
                return func(obj, *args, **kwargs)

        return self._base_func(obj, *args, **kwargs)


def lazydispatch(arg=None, *, scope: Optional[str] = None) -> LazyDispatcher:
    if not isinstance(arg, type) and callable(arg):
        # Case: used as @lazydispatch without arguments
        return LazyDispatcher(arg, scope=scope)

    # Case: used as @lazydispatch("type.path", scope=...)
    def wrapper(func):
        key = _qualify(func, scope)
        if key not in GLOBAL_DISPATCHERS:
            GLOBAL_DISPATCHERS[key] = LazyDispatcher(func, scope)
        dispatcher = GLOBAL_DISPATCHERS[key]
        return dispatcher._register(arg, func)

    return wrapper


_QUALNAME_RE = re.compile(r'^[a-zA-Z_][\w\.]*\.[A-Z_a-z]\w*$')


def is_valid_qualname(s: str) -> bool:
    """
    Check if a string looks like a valid qualified name for a type.

    A valid qualname is expected to have:
      - one or more dot-separated components
      - all parts must be valid identifiers
      - the final part (the type name) must start with a letter or underscore

    Examples:
        >>> is_valid_qualname('torch.Tensor')
        True
        >>> is_valid_qualname('numpy.ndarray')
        True
        >>> is_valid_qualname('builtins.int')
        True
        >>> is_valid_qualname('not.valid.')
        False
        >>> is_valid_qualname('1bad.name')
        False
        >>> is_valid_qualname('no_dot')
        False
    """
    return bool(_QUALNAME_RE.match(s))
