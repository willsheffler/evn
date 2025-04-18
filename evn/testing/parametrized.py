import copy
import functools
import typing as t
import evn

T = t.TypeVar('T')

def make_parametrized_tests(namespace: t.MutableMapping,
                            args: list[T],
                            prefix: str = 'helper_test_',
                            make_testdata: t.Callable[[T], t.Any] = lambda x: x,
                            debug=False,
                            **kw):
    for arg in args:

        @evn.chrono
        def run_convert(arg, kw=kw):
            return evn.kwcall(kw, make_testdata, arg)

        @functools.cache
        def processed(arg=arg):
            return run_convert(arg)

        for helpername, helperfunc in list(namespace.items()):
            if helpername.startswith(prefix):
                testname = f"{helpername[prefix.find('test_'):]}_{str(arg).upper()}"

                def testfunc(arg=arg, helperfunc=helperfunc, processed=processed, kw=kw):
                    return evn.kwcall(kw, helperfunc, copy.copy(processed()))

                # c = ipd.dev.timed(lambda arg, kw=kw: ipd.kwcall(kw, make_testdata, arg), testname=f'{testname}_setup')
                # testfunc = lambda helperfunc=helperfunc, arg=arg, c=c, kw=kw: ipd.kwcall(kw, helperfunc, c(arg))
                testfunc.__name__ = testfunc.__qualname__ = testname
                namespace[testname] = testfunc
                if debug: print(f'ADD_PARAMETRIC_TEST {testname}')
