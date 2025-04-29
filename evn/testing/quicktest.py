import sys
import time
import inspect
# from doctest import testmod
import typing
import tempfile
import pytest
import io
import evn

T = typing.TypeVar('T')

class TestConfig(evn.Bunch):

    def __init__(self, *a, **kw):
        super().__init__(self, *a, **kw)
        self.nofail = self.get('nofail', False)
        self.debug = self.get('debug', False)
        self.checkxfail = self.get('checkxfail', False)
        self.timed = self.get('timed', True)
        self.nocapture = self.get('nocapture', [])
        self.fixtures = self.get('fixtures', {})
        self.setup = self.get('setup', lambda: None)
        self.funcsetup = self.get('funcsetup', lambda: None)
        self.context = self.get('context', evn.nocontext)
        self.use_test_classes = self.get('use_test_classes', True)
        self.dryrun = self.get('dryrun', False)

    def detect_fixtures(self, namespace):
        if not evn.ismap(namespace):
            namespace = vars(namespace)
        for name, obj in namespace.items():
            if callable(obj) and hasattr(obj, '_pytestfixturefunction'):
                assert name not in self.fixtures
                self.fixtures[name] = obj.__wrapped__()  #type:ignore

@evn.struct
class TestResult:
    passed: list[str] = evn.field(list)
    failed: list[str] = evn.field(list)
    errored: list[str] = evn.field(list)
    xfailed: list[str] = evn.field(list)
    skipexcn: list[str] = evn.field(list)
    _runtime: dict[str, float] = evn.field(dict)

    def runtime(self, name: str) -> float:
        return self._runtime[name]

    def items(self) -> list[tuple[str, list[str]]]:
        return [
            ('passed', self.passed),
            ('failed', self.failed),
            ('errored', self.errored),
            ('xfailed', self.xfailed),
            ('skipexcn', self.skipexcn),
        ]

@evn.chrono
def quicktest(namespace, config=evn.Bunch(), **kw):
    t_start = time.perf_counter()
    namespace, config = configure(namespace, config, **kw)
    namespace = evn.kwcall(config, evn.meta.filter_namespace_funcs, namespace)
    test_funcs, teardown = collect_tests(namespace, config)
    try:
        result = run_tests(test_funcs, config, kw)
    finally:
        for func in teardown:
            func()
    print_result(config, result, time.perf_counter() - t_start)
    return result


def configure(namespace, config, **kw):
    orig = namespace
    if not evn.ismap(namespace):
        namespace = vars(namespace)
    if '__file__' in namespace:
        print(f'quicktest "{namespace["__file__"]}":', flush=True)
    else:
        print(f'quicktest "{orig}":', flush=True)
    config = TestConfig(**config, **kw)
    config.detect_fixtures(namespace)
    return namespace, config

def print_result(config, result, t_total):
    if result.passed:
        print(f'PASSED {len(result.passed)} tests in {t_total:.3f} seconds')
    result.passed.sort(key=result.runtime, reverse=True)
    npassprinted = 0
    for label, tests in result.items():
        for test in tests:
            if label == 'passed' and not config.debug and npassprinted > 9 and result._runtime[test] < 100:
                npassprinted += 1
                continue
            print(f'{label.upper():9} {result._runtime[test]*1000:7.3f} ms {test}', flush=True)

def func_ok_for_testing(name, obj):
    return name.startswith('test_') and callable(obj) and evn.testing.no_pytest_skip(obj)

def class_ok_for_testing(name, obj):
    return name.startswith('Test') and isinstance(obj, type) and not hasattr(obj, '__unittest_skip__')

@evn.chrono
def collect_tests(namespace, config):
    test_funcs, test_classes, teardown = [], [], []
    for name, obj in namespace.items():
        if class_ok_for_testing(name, obj) and config.use_test_classes:
            suite = obj()
            test_classes.append(suite)
            # print(f'{f" obj: {name} ":=^80}', flush=True)
            test_methods = evn.meta.filter_namespace_funcs(vars(namespace[name]))
            test_methods = {
                f'{name}.{k}': getattr(suite, k)
                for k, v in test_methods.items() if func_ok_for_testing(k, v)
            }
            # TODO: maybe call these lazilyt?
            getattr(suite, 'setUp', lambda: None)()
            # test_suites.append((name, obj))
            test_funcs.extend(test_methods.items())
            teardown.append(getattr(suite, 'tearDown', lambda: None))
        elif func_ok_for_testing(name, obj):
            test_funcs.append((name, obj))
    testmodule = evn.Path(inspect.getfile(test_funcs[0][1])).stem
    for _, func in test_funcs:
        if evn.is_free_function(func):
            func.__module__ = func.__module__.replace('__main__', testmodule)
    for obj in test_classes:
        obj.__module__ = obj.__module__.replace('__main__', testmodule)
    return test_funcs, teardown

@evn.chrono
def run_tests(test_funcs, config, kw):
    result = TestResult()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = evn.Path(tmpdir)
        evn.kwcall(config.fixtures, config.setup)
        config.fixtures['tmpdir'] = str(tmpdir)
        config.fixtures['tmp_path'] = tmpdir
        for name, func in test_funcs:
            quicktest_run_maybe_parametrized_func(name, func, result, config, kw)
    return result

@evn.chrono
def quicktest_run_maybe_parametrized_func(name, func, result, config, kw):
    names, values = evn.testing.get_pytest_params(func) or ((), [()])
    for val in values:
        if len(names) == 1 and not isinstance(val, (list, tuple)):
            val = [val]
        paramkw = kw | dict(zip(names, val))
        quicktest_run_test_function(name, func, result, config, paramkw)

@evn.chrono
def quicktest_run_test_function(name, func, result, config, kw, check_xfail=True):
    error, testout = None, None
    nocapture = config.nocapture is True or name in config.nocapture
    capture_ctx = evn.nocontext if nocapture else evn.capture_stdio
    chrono_ctx = evn.chronometer.scope if config.timed else evn.nocontext
    with capture_ctx() as testout, chrono_ctx(name) as timer:  # noqa
        try:
            evn.kwcall(config.fixtures, config.funcsetup)
            if not config.dryrun:
                kwthis = evn.kwcheck(config.fixtures | kw, func)
                t_start = time.perf_counter()
                func(**kwthis)
                result._runtime[name] = time.perf_counter() - t_start
                result.passed.append(name)
        except pytest.skip.Exception:
            result.skipexcn.append(name)
        except AssertionError as e:
            if evn.testing.has_pytest_mark(func, 'xfail'):
                result.xfailed.append(name)
            else:
                result.failed.append(name)
            error = e
        except Exception as e:  # noqa
            result.errored.append(name)
            error = e
    if any([
            name in result.failed,
            name in result.errored,
            config.checkxfail and name in result.xfailed,
    ]):
        print(f'{f" {func.__name__} ":-^80}', flush=True)
        if testout: print(testout.read(), flush=True, end='')
        if config.nofail and error: print(error)
        elif error: raise error

class CapSys:

    def __enter__(self):
        self._stdout = io.StringIO()
        self._stderr = io.StringIO()
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr

    def readouterr(self):
        self._stdout.seek(0)
        self._stderr.seek(0)
        return CapResult(self._stdout.read(), self._stderr.read())

class CapResult:

    def __init__(self, out, err):
        self.out = out
        self.err = err
