import pytest
from typing import Optional, Union

import evn
from evn.meta.kwargs_tunnel import kwcheck, kwcall, kwargs_acceptor, _is_type_compatible

def main():
    evn.testing.quicktest(globals())

def test_kwcheck_passes_through_valid_kwargs():

    def f(a, b=1):
        return a + b

    result = kwcheck({'a': 2, 'b': 3}, f)
    assert result == {'a': 2, 'b': 3}

def test_kwcheck_filters_invalid_kwargs():

    def f(x):
        return x

    result = kwcheck({'x': 42, 'extra': 99}, f, check_typos=False)
    assert result == {'x': 42}

def test_kwcheck_raises_on_typo():

    def f(alpha):
        return alpha

    with pytest.raises(TypeError) as excinfo:
        kwcheck({'alpah': 10}, f, check_typos=True)
    assert "alpah" in str(excinfo.value)
    assert "Did you mean 'alpha'" in str(excinfo.value)

def test_kwcall_invokes_function_correctly():

    def f(x, y=0):
        return x + y

    result = kwcall({'x': 3}, f, y=2)
    assert result == 5

def test_kwcall_filters_and_merges():

    def f(a, b):
        return a * b

    result = kwcall({'a': 4, 'c': 99}, f, b=2)
    assert result == 8

def test_kwargs_acceptor_decorator_behavior():
    calls = []

    @kwargs_acceptor
    def g(a, b=0):
        calls.append((a, b))
        return a - b

    assert g(a=5, b=2, c="ignored") == 3  # type:ignore
    assert g(a=5, b=2, **{'c': 'ignored'}) == 3
    assert calls[-1] == (5, 2)

def test_is_type_compatible_basic():
    assert _is_type_compatible(10, int)
    assert not _is_type_compatible("x", int)

def test_is_type_compatible_optional():
    assert _is_type_compatible(None, Optional[int])
    assert _is_type_compatible(5, Optional[int])

def test_is_type_compatible_union():
    assert _is_type_compatible("abc", Union[int, str])
    assert not _is_type_compatible([], Union[int, str])

def test_is_type_compatible_fallback_on_typeerror():
    # Should return True even if expected_type is not suitable for isinstance
    class Dummy:
        pass

    assert _is_type_compatible(Dummy(), list[int])  # triggers TypeError internally

if __name__ == '__main__':
    main()
