import types as t
import os
from multipledispatch import dispatch
import rich
from evn._prelude.lazy_dispatch import lazydispatch
from evn._prelude.basic_types import is_member_function

import evn

def inspect(obj, **kw):
    return show_impl(obj, **kw)

def show(obj, out=print, **kw):
    with evn.capture_stdio() as printed:
        result = show_impl(obj, **kw)
    printed = printed.read()
    assert not result
    if out and (result or printed):
        with evn.force_stdio():
            if 'PYTEST_CURRENT_TEST' in os.environ: print()
            kwout = evn.kwcheck(kw, out)
            out(printed or result, **kwout)
    return result

_show = show

def diff(obj1, obj2, out=print, **kw):
    result = diff_impl(obj1, obj2, **kw)
    if out and result: _show(result, **kw)
    return result

@lazydispatch
def summary(obj, **kw) -> str:
    if hasattr(obj, 'summary'): return obj.summary()
    if isinstance(obj, (list, tuple)): return str([summary(o, **kw) for o in obj])
    return str(obj)


@dispatch(object)
def show_impl(obj, **kw):
    """Default show function."""
    evn.kwcall(kw, rich.inspect, obj)

@dispatch(object, object)
def diff_impl(obj1, obj2, **kw):
    return set(obj1) ^ set(obj2)

@summary.register(t.FunctionType)
def _(obj):
    return f'{obj.__module__}.{obj.__qualname__}'.replace('.<locals>','')

@summary.register(t.MethodType)
def _(obj):
    return f'{obj.__module__}.{obj.__qualname__}'.replace('.<locals>','')

@summary.register('numpy.ndarray')
def _(array, maxnumel=24):
    if array.size <= maxnumel:
        return str(array)
    return f'{array.__class__.__name__}{list(array.shape)}'

@summary.register('torch.Tensor')
def _(tensor, maxnumel=24):
    if tensor.numel <= maxnumel:
        return str(tensor)
    return f'{tensor.__class__.__name__}{list(tensor.shape)}'

_trace_indent = 0

def trace(func, showargs=True, showreturn=True, **kw):
    """Decorator to show function output."""
    def wrapper(*args, **kwargs):
        if not evn.show_trace:
            return func(*args, **kwargs)
        global _trace_indent
        indent = '    ' * _trace_indent
        if showargs:
            sargs = args[1:] if is_member_function(func) else args
            argstr = ''
            argstr = [summary(a) for a in sargs] + [f'{k}={summary(v)}' for k, v in kwargs.items()]
            argstr = f'({", ".join(argstr)})'
        print(f'{indent}call: {func.__name__}{argstr}')
        _trace_indent += 1
        result = func(*args, **kwargs)
        _trace_indent -= 1
        returnstr = ''
        if showreturn and result is not None:
            returnstr = f' -> {summary(result, **kw)}'
            print(f'{indent}return: {func.__name__}{returnstr}')
        if result: summary(result, **kw)
        return result
    return wrapper
