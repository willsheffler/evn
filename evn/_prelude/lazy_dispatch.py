import re
import contextlib
import sys
from functools import wraps
import typing as t


GLOBAL_DISPATCHERS: dict[str, 'LazyDispatcher'] = {}

class NoType:
    pass

class NoPredType:

    def __call__(self, typ: type) -> bool:
        return False

NoPred = NoPredType()

def _qualify_scope(func: t.Callable, scope: str) -> str:
    mod = func.__module__
    name = func.__name__
    qname = func.__qualname__
    if scope == 'local' or scope not in ['global', 'project', 'subpackage']:
        return f'{mod}.{qname}'
    elif scope == 'global':
        return name
    elif scope == 'project':
        parts = mod.split('.')
        root = parts[0] if parts else mod
        return f'{root}.{name}'
    else:
        parts = mod.split('.')
        subpkg = '.'.join(parts[:-1])
        return f'{subpkg}.{name}'

class LazyDispatcher:

    def __init__(self, func: t.Callable, scope: str = 'global'):
        self._base_func = func
        self._registry: dict[t.Union[str, type], t.Callable] = {}
        self._predicate_registry: dict[t.Callable[[type], bool], t.Callable] = {}
        self._resolved_types = {}
        self._key = _qualify_scope(func, scope)
        self.slow: set[str | object] = {'torch', 'numpy', 'pandas', 'matplotlib', 'scipy'}
        wraps(func)(self)

        # GLOBAL_DISPATCHERS[self._key] = self

    def _register(
        self,
        func: t.Callable,
        typ: t.Union[str, type] = NoType,
        predicate: t.Callable[[type], bool] = NoPred,
        slow=False,
    ) -> 'LazyDispatcher':
        if typ is object: self._base_func = func
        elif predicate is NoPred: self._registry[typ] = func
        else: self._predicate_registry[predicate] = func
        if slow: self.slow.add(typ)
        return self

    def register(self,
                 typ: t.Union[str, type] = NoType,
                 predicate: t.Callable[[type], bool] = NoPred,
                 slow=False,
                 scope: str = '') -> t.Callable[[t.Any], 'LazyDispatcher']:

        def decorator(func):
            result = self._register(func, typ, predicate, slow=slow)
            return result

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
                        self._registry[self._resolved_types[typ]] = self._registry[typ]

    def __call__(self, obj, *args, debug=False, **kwargs):
        self._resolve_lazy_types()

        # TODO: make predicate work with obj, eg. floats > 7

        if (obj_type := type(obj)) in self._registry:
            if debug: print('in registery')
            return self._registry[obj_type](obj, *args, **kwargs)

        for pred, func in self._predicate_registry.items():
            if pred(obj):
                if debug: print('select by predicates', pred, obj)
                self._registry[type(obj)] = func
                return func(obj, *args, **kwargs)
        for slow in (False, True):
            for key, func in list(self._registry.items()):
                if isinstance(key, str):
                    if slow and key.split('.')[0] not in self.slow: continue
                    if not slow and key.split('.')[0] in self.slow: continue
                if debug: print('unfound key', key, obj)
                if key := self.check_type(key):
                    if isinstance(obj, key):
                        self._registry[type(obj)] = func
                        return func(obj, *args, **kwargs)

        return self._base_func(obj, *args, **kwargs)

    def check_type(self, key):
        if isinstance(key, type): return key
        if isinstance(key, str):
            modname, _, _typename = key.rpartition('.')
            if modname not in sys.modules: return None
            self._resolve_lazy_types()
            return self._resolved_types.get(key, None)
        # raise TypeError(f'Key {key} is not a type or str of type')

Deco = t.Callable[[t.Any], LazyDispatcher]

@t.overload
def lazydispatch(arg: t.Callable[[t.Any], t.Any]) -> LazyDispatcher:
    ...

@t.overload
def lazydispatch(arg: type | str) -> Deco:
    ...

@t.overload
def lazydispatch(arg: type | str = NoType, *, scope: str) -> Deco:
    ...

@t.overload
def lazydispatch(arg: type | str = NoType, *, predicate: t.Callable[[t.Any], bool]) -> Deco:
    ...

@t.overload
def lazydispatch(arg: type | str = NoType, *, predicate: t.Callable[[t.Any], bool], scope: str) -> Deco:
    ...

def lazydispatch(
    arg: type | str | t.Callable[[t.Any], t.Any] = NoType,
    *,
    predicate: t.Callable[[type], bool] = NoPred,
    scope: str = 'global',
) -> LazyDispatcher | t.Callable[[t.Any], LazyDispatcher]:
    if not isinstance(arg, type) and callable(arg) and predicate == NoPred and scope == 'global':
        # Case: used as @lazydispatch without arguments
        return LazyDispatcher(arg)
    type_ = arg
    assert isinstance(type_, (type(None), str, type)), f'Expected type or str, got {type(type_)}'

    # Case: used as @lazydispatch("type", scope=...)
    def wrapper(func) -> LazyDispatcher:
        key = _qualify_scope(func, scope)
        if key not in GLOBAL_DISPATCHERS:
            GLOBAL_DISPATCHERS[key] = LazyDispatcher(func, scope)
        dispatcher = GLOBAL_DISPATCHERS[key]
        return dispatcher._register(func, type_, predicate=predicate)

    return wrapper

# @make_decorator(
#     predicate=NoPred,
#     scope=None,
# )
# def lazydispatch(wrapped, *args, predicate, scope, **kw):
#         key = _qualify_scope(func, scope)
#         if key not in GLOBAL_DISPATCHERS:
#             GLOBAL_DISPATCHERS[key] = LazyDispatcher(func, scope)
#         dispatcher = GLOBAL_DISPATCHERS[key]
#         return dispatcher._register(func, arg, predicate=predicate)

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
