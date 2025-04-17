import inspect
from typing import Any, Callable, Dict, Optional, TypeVar, Union, ParamSpec
from evn._prelude.make_decorator import make_decorator

T = TypeVar('T')
P = ParamSpec('P')
R = TypeVar('R')
KW = Dict[str, Any]

@make_decorator(check_typos=True, type_check=False)
def kwargs_acceptor(wrapped: Callable[P, R],
                    *args,
                    check_typos: bool = True,
                    type_check: bool = False,
                    **kw) -> R:
    filtered_kwargs = kwcheck(kw, wrapped, check_typos=check_typos, type_check=type_check)
    return wrapped(*args, **filtered_kwargs)

def kwcheck(kw: KW, func: Optional[Callable] = None, check_typos: bool = True, type_check=False) -> KW:
    """Filter keyword arguments to match those accepted by a function.

    Args:
        kw: Dictionary of keyword arguments to filter
        func: The function whose signature defines accepted parameters
        check_typos: If True, raises TypeError for arguments that look like typos

    Returns:
        Filtered dictionary containing only accepted keyword arguments
    """
    if func is None: return kw
    sig = inspect.signature(func)
    params = sig.parameters
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if accepts_kwargs: return kw
    valid_params = {
        name
        for name, param in params.items()
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    filtered_kw = {k: v for k, v in kw.items() if k in valid_params}
    if check_typos:
        if invalid_keys := set(kw.keys()) - valid_params:
            # Check for possible typos (keys that look similar to valid params)
            for invalid_key in invalid_keys:
                if close_matches := [valid for valid in valid_params if _similar_strings(invalid_key, valid)]:
                    suggestions = ', '.join(f"'{match}'" for match in close_matches)
                    raise TypeError(f"'{invalid_key}' is not a valid parameter for {func.__name__}. "
                                    f'Did you mean {suggestions}?')
    if type_check:
        assert 0

    return filtered_kw

def _similar_strings(a: str, b: str, threshold: float = 0.8) -> bool:
    """Check if two strings are similar using a simple metric.

    This is a basic implementation that could be replaced with more
    sophisticated algorithms like Levenshtein distance.
    """
    # Simple implementation - just check if one string is contained in the other
    # or if they share many characters
    if a in b or b in a: return True
    common = set(a) & set(b)
    similarity = len(common) / ((len(a) + len(b)) / 2)
    return similarity >= threshold

def kwcall(kw: KW, func: Callable[P, R], *args: Any, **kwargs: Any) -> R:
    """Call a function with filtered keyword arguments.

    Args:
        kw: Primary dictionary of keyword arguments
        func: The function to call
        *args: Positional arguments to pass to the function
        **kwargs: Additional keyword arguments that will be merged with kw

    Returns:
        The return value from calling func
    """
    merged_kwargs = {**kw, **kwargs}
    filtered_kwargs = kwcheck(merged_kwargs, func)
    return func(*args, **filtered_kwargs)

def _is_type_compatible(value: Any, expected_type: Any) -> bool:
    """Check if a value is compatible with an expected type."""
    if (hasattr(expected_type, '__origin__') and expected_type.__origin__ is Union
            and type(None) in expected_type.__args__):
        if value is None:
            return True
        other_types = [t for t in expected_type.__args__ if t is not type(None)]
        return any(_is_type_compatible(value, t) for t in other_types)
    elif hasattr(expected_type, '__origin__') and expected_type.__origin__ is Union:
        return any(_is_type_compatible(value, arg) for arg in expected_type.__args__)
    try:
        return isinstance(value, expected_type)
    except TypeError:
        # Some types like List[int] will cause TypeError with isinstance
        # In these cases, we just return True to avoid false positives
        return True
