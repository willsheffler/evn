import inspect
import click
import typing
from functools import wraps

from evn.cli.click_type_handler import ClickTypeHandlers

def _extract_annotation(annotation):
    """
    If the annotation is a typing.Annotated, split it into base type and metadata.
    Otherwise, return the annotation and None.
    """
    if typing.get_origin(annotation) is typing.Annotated:
        if args := typing.get_args(annotation):
            return args[0], annotation, args[1:]
    return annotation, None, None

def _generate_click_decorator(name, param, type_handlers: ClickTypeHandlers):
    """
    Given a parameter (an inspect.Parameter object) and a list of type handlers,
    generate a Click decorator (click.argument for required parameters, click.option for optional ones)
    for that parameter.
    """
    basetype, annotation, metadata = _extract_annotation(param.annotation)
    # Determine the Click ParamType via our type handlers.

    param_type = type_handlers.typehint_to_click_paramtype(basetype, metadata)
    if not param_type and type_handlers:
        raise ValueError(
            f"No suitable Click ParamType found for basetype {basetype} annotation '{annotation}' with metadata '{metadata}' {type_handlers}"
        )

    has_default = (param.default != inspect.Parameter.empty)
    # For booleans, always use option with is_flag=True.
    if basetype is bool and not metadata:
        deco = click.option(f"--{name.replace('_', '-')}", is_flag=True, default=param.default)
    elif not has_default and param_type:
        deco = click.argument(name, type=param_type)
    elif not has_default:
        deco = click.argument(name)
    else:
        option_names = [f"--{name.replace('_', '-')}"]
        kwargs = {"default": param.default, "show_default": True}
        if param_type:
            kwargs["type"] = param_type
        if annotation is bool:
            kwargs["is_flag"] = True
        deco = click.option(*option_names, **kwargs)
    # ic(name, type(deco))
    return deco

def auto_click_decorate_command(fn, type_handlers: ClickTypeHandlers):
    """
    Auto-decorate a function with Click parameter decorators based on its signature.

    This function inspects the signature of fn and automatically generates decorators
    (click.argument for required parameters, click.option for parameters with defaults)
    for every public parameter (ignoring those whose names start with '_') that is not already
    manually decorated.

    Additionally, for parameters whose names start with "_" (internal parameters) that lack a default,
    a wrapper is added to supply None when they are missing from the CLI input.

    Raises a RuntimeError if fn is already a full Click command (i.e. if isinstance(fn, click.Command)),
    ensuring that our framework controls command creation.
    """
    if isinstance(fn, click.Command):
        raise RuntimeError(
            "Function is already a full Click command; manual @click.command decorators are not allowed.")

    sig = inspect.signature(fn)
    # Collect names of parameters that already have manual Click decoration.
    manual_params = set()
    if hasattr(fn, "__click_params__"):
        for p in fn.__click_params__:
            if hasattr(p, "name") and p.name:
                manual_params.add(p.name)

    decorators = []
    params = list(sig.parameters.items())
    if params and params[0][0] == "self":
        params = params[1:]  # Skip "self"

    for name, param in params:
        if name.startswith("_"):
            continue  # We'll handle internals separately.
        if name in manual_params:
            continue
        decorator = _generate_click_decorator(name, param, type_handlers)
        decorators.append(decorator)

    # Apply the parameter decorators.
    for decorator in reversed(decorators):
        fn = decorator(fn)

    # Wrap the function to supply None for any internal parameter missing a default.
    orig_sig = inspect.signature(fn)
    internal_params = [
        name for name, param in orig_sig.parameters.items()
        if name.startswith("_") and param.default == inspect.Parameter.empty
    ]
    if internal_params:
        original_fn = fn  # capture the function before wrapping to avoid recursion

        @wraps(original_fn)
        def wrapper(*args, **kwargs):
            for name in internal_params:
                if name not in kwargs:
                    kwargs[name] = None
            return original_fn(*args, **kwargs)

        fn = wrapper

    return fn
