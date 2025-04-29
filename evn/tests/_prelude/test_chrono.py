from pprint import pprint
import statistics
import pytest
import time
import random
from evn._prelude.chrono import Chrono, chrono, ChronoScope
# from evn.dynamic_float_array import DynamicFloatArray

import evn

# orig_name = __name__
# __name__ = 'test_chrono'

config_test = evn.Bunch(
    re_only=[
        #
    ],
    re_exclude=[
        #
    ],
)

chronometer = Chrono('test_chrono')

def main():
    evn.testing.quicktest(
        namespace=globals(),
        config=config_test,
        verbose=1,
        check_xfail=False,
        chrono=False,
    )

def make_nested_calls(c):
    with c.scope('foo'):
        time.sleep(0.004)
        with c.scope('bar'):
            time.sleep(0.003)
            with c.scope('baz'):
                time.sleep(0.004)
            time.sleep(0.003)
        time.sleep(0.004)
    return dict(foo=0.008, bar=0.006, baz=0.004)

def test_chronometer():
    assert evn.chronometer

class FuncNest:

    def __init__(self):
        self.runtime = {'method1': [], 'method2': [], 'method3': [], 'recursive': [], 'generator': []}
        self.tottime = {'method1': [], 'method2': [], 'method3': [], 'recursive': [], 'generator': []}

    @chrono(chrono=chronometer)
    def method1(self):
        start = start_tot = time.perf_counter()
        time.sleep(0.0025)  # random.uniform(0.0025, 0.03))
        self.runtime['method1'].append(time.perf_counter() - start)
        self.method2()
        start = time.perf_counter()
        time.sleep(0.0025)  # random.uniform(0.0025, 0.03))
        self.runtime['method1'].append(time.perf_counter() - start)
        self.method3()
        start = time.perf_counter()
        time.sleep(0.0025)  # random.uniform(0.0025, 0.03))
        self.runtime['method1'].append(time.perf_counter() - start)
        self.method3()
        start = time.perf_counter()
        time.sleep(0.0025)  # random.uniform(0.0025, 0.03))
        self.runtime['method1'].append(time.perf_counter() - start)
        self.tottime['method1'].append(time.perf_counter() - start_tot)

    @chrono(chrono=chronometer)
    def method2(self):
        start = start_tot = time.perf_counter()
        time.sleep(0.005)  # random.uniform(0.01, 0.03))
        self.runtime['method2'].append(time.perf_counter() - start)
        self.recursive(3, topcall=True)
        start = time.perf_counter()
        time.sleep(0.005)  # random.uniform(0.01, 0.03))
        self.runtime['method2'].append(time.perf_counter() - start)
        self.tottime['method2'].append(time.perf_counter() - start_tot)

    @chrono(chrono=chronometer)
    def method3(self):
        start = start_tot = time.perf_counter()
        time.sleep(0.005)
        self.runtime['method3'].append(time.perf_counter() - start)
        self.tottime['method3'].append(time.perf_counter() - start_tot)

    @chrono(chrono=chronometer)
    def recursive(self, depth, topcall=False):
        if not depth: return
        start = start_tot = time.perf_counter()
        time.sleep(0.005)  # random.uniform(0.005, 0.03))
        self.runtime['recursive'].append(time.perf_counter() - start)
        self.recursive(depth - 1)
        start = time.perf_counter()
        time.sleep(0.005)  # random.uniform(0.005, 0.03))
        self.runtime['recursive'].append(time.perf_counter() - start)
        if topcall: self.tottime['recursive'].append(time.perf_counter() - start_tot)

    # @chrono(chrono=chronometer)
    # def generator(self):
    #     start = time.perf_counter()
    #     time.sleep(0.01)  # random.uniform(0.01, 0.03))
    #     self.runtime['generator'].append(time.perf_counter() - start)
    #     for i in range(5):
    #         start = time.perf_counter()
    #         time.sleep(0.01)  # random.uniform(0.01, 0.03))
    #         self.runtime['generator'].append(time.perf_counter() - start)
    #         yield i
    #         start = time.perf_counter()
    #         time.sleep(0.01)  # random.uniform(0.01, 0.03))
    #         self.runtime['generator'].append(time.perf_counter() - start)

FuncNest.__module__ = 'test_chrono'
FuncNest.method1.__module__ = 'test_chrono'
FuncNest.method2.__module__ = 'test_chrono'
FuncNest.recursive.__module__ = 'test_chrono'

# FuncNese.generator.__module__ = 'test_chrono'

@pytest.mark.noci
def test_chrono_nesting():
    chronometer.clear()
    instance = FuncNest()
    instance.method1()
    # assert list(instance.generator()) == [0, 1, 2, 3, 4]
    report = chronometer.report_dict()
    # pprint(report)
    for method in 'method1 method2 recursive'.split():
        try:
            recorded = sum(instance.runtime[method])
            recorded_tot = sum(instance.tottime[method])
            # print(report.keys())
            chrono = report[f'test_chrono.FuncNest.{method}'].active
            chrono_tot = report[f'test_chrono.FuncNest.{method}'].total
            err = f'Mismatch in active {method}, internal: {recorded} vs chrono: {chrono}'
            assert abs(recorded - chrono) < 0.001, err
            err = f'Mismatch in total {method}, internal: {recorded_tot} vs chrono: {chrono_tot}'
            assert abs(recorded_tot - chrono_tot) < 0.001, err
        except KeyError:
            assert 0, f'missing key {method}'
    ttot = evn.Bunch(chronometer.times_tot)
    tot_meth2 = sum(ttot['test_chrono.FuncNest.method2'])
    tot_meth1 = sum(ttot['test_chrono.FuncNest.method1'])
    tot_rec = sum(ttot['test_chrono.FuncNest.recursive'])
    assert tot_meth2 < tot_meth1, f'tot_meth2 {tot_meth2} >= tot_meth1 {tot_meth1}'
    assert tot_rec < tot_meth2, f'tot_rec {tot_rec} >= tot_meth2 {tot_meth2}'
    t_rec_active = sum(chronometer.times['test_chrono.FuncNest.recursive'])
    assert abs(tot_rec - t_rec_active) < 0.001, f'tot_rec {tot_rec} != t_rec_active {t_rec_active}'
    assert chronometer.scopestack[-1].name == chronometer.name

def test_chrono_func():
    chronometer = Chrono()

    @chrono(chrono=chronometer)(chrono=chronometer)
    def foo():
        time.sleep(0.001)

    foo.__module__ = 'test_chrono'
    foo()
    assert 'test_chrono.test_chrono_func.foo' in chronometer.times
    assert len(chronometer.times['test_chrono.test_chrono_func.foo']) == 1
    print(chronometer.times['test_chrono.test_chrono_func.foo'])
    assert sum(chronometer.times['test_chrono.test_chrono_func.foo']) >= 0.001

def test_scope():
    with Chrono() as t:
        t.enter_scope('foo')
        t.enter_scope('bar')
        t.enter_scope('baz')
        t.exit_scope('baz')
        t.exit_scope('bar')
        t.exit_scope('foo')
    assert 'foo' in t.times
    assert 'bar' in t.times
    assert 'baz' in t.times

def allclose(a, b, atol):
    if isinstance(a, float): return abs(a - b) < atol
    return all(abs(a - b) <= atol for x, y in zip(a, b))

@pytest.mark.noci
def test_chrono_checkpoint():
    with Chrono() as chrono:
        time.sleep(0.002)
        chrono.checkpoint('foo')
        time.sleep(0.006)
        chrono.checkpoint('bar')
        time.sleep(0.004)
        chrono.checkpoint('baz')

    times = chrono.report_dict()
    assert allclose(times['foo'].active, 0.002, atol=0.005)
    assert allclose(times['bar'].active, 0.006, atol=0.005)
    assert allclose(times['baz'].active, 0.004, atol=0.005)

    times = chrono.report_dict(order='active')
    assert list(times.keys()) == ['total', 'bar', 'baz', 'foo', 'Chrono'], f'Unexpected keys: {times.keys()}'

    times = chrono.report_dict(order='callorder')
    print(times.keys())
    assert list(times.keys()) == ['foo', 'bar', 'baz', 'total', 'Chrono'], f'Unexpected keys: {times.keys()}'

    with pytest.raises(ValueError):
        chrono.report_dict(order='oarenstoiaen')

def chrono_deco_func():
    time.sleep(0.01)

chrono_deco_func.__module__ = 'test_chrono'
chrono_deco_func = chrono(chrono_deco_func, chrono=chronometer)

def test_chrono_deco_func():
    chronometer.clear()
    for _ in range(3):
        chrono_deco_func()

    times = chronometer.find_times('test_chrono.chrono_deco_func')
    for t in times:
        assert 0.01 <= t < 0.012
    assert 'test_chrono.chrono_deco_func' in chronometer.times

def chrono_deco_func2():
    time.sleep(0.005)
    chrono_deco_func()
    time.sleep(0.005)

chrono_deco_func2.__module__ = 'test_chrono'
chrono_deco_func2 = chrono(chrono_deco_func2, chrono=chronometer)

def chrono_deco_func3():
    time.sleep(0.005)
    chrono_deco_func2()
    time.sleep(0.005)

chrono_deco_func3.__module__ = 'test_chrono'
chrono_deco_func3 = chrono(chrono_deco_func3, chrono=chronometer)

def test_chrono_deco_func_nest():
    chronometer.clear()
    N = 1
    for _ in range(N):
        chrono_deco_func3()
    times = chronometer.find_times('test_chrono.chrono_deco_func')
    times2 = chronometer.find_times('test_chrono.chrono_deco_func2')
    times3 = chronometer.find_times('test_chrono.chrono_deco_func3')
    print(chronometer.times.keys())
    assert N == len(times) == len(times2) == len(times3)
    for t, t2, t3 in zip(times, times2, times3):
        assert 0.01 <= t < 0.012
        assert 0.01 <= t2 < 0.012
        assert 0.01 <= t3 < 0.012
    assert 'test_chrono.chrono_deco_func' in chronometer.times
    assert 'test_chrono.chrono_deco_func2' in chronometer.times

@pytest.mark.noci
def test_summary():
    with Chrono() as chrono:
        chrono.enter_scope('foo')
        time.sleep(0.001)
        chrono.exit_scope('foo')
        chrono.enter_scope('foo')
        time.sleep(0.003)
        chrono.exit_scope('foo')
        chrono.enter_scope('foo')
        time.sleep(0.002)
        chrono.exit_scope('foo')
    times = chrono.report_dict(summary=sum)
    assert allclose(times['foo'].active, 0.006, atol=0.002)

    times = chrono.report_dict(summary=statistics.mean)
    assert allclose(times['foo'].active, 0.002, atol=0.001)

    times = chrono.report_dict(summary=min)
    assert allclose(times['foo'].active, 0.001, atol=0.001)

    with pytest.raises(TypeError):
        chrono.report(summary='foo')

    with pytest.raises(TypeError):
        chrono.report(summary=1)

def test_chrono_stop_behavior():
    chrono = Chrono()
    chrono.enter_scope('foo')
    chrono.exit_scope('foo')
    chrono.stop()
    assert chrono.stopped
    with pytest.raises(AssertionError):
        chrono.enter_scope('bar')
    with pytest.raises(AssertionError):
        chrono.end_scope(ChronoScope('baz', chrono))

def test_scope_mismatch():
    chrono = Chrono()
    chrono.enter_scope('foo')
    with pytest.raises(AssertionError, match='exiting scope: bar doesnt match: foo'):
        chrono.exit_scope('bar')

def test_scope_name_from_object():
    chrono = Chrono()

    class Dummy:
        pass

    name = chrono.scope_name(Dummy)
    assert isinstance(name, str)
    assert 'Dummy' in name

@pytest.mark.skip
def test_generator_deco():
    calls = []

    @chrono(chrono=chronometer)
    def gen():
        yield 1
        yield 2

    with pytest.raises(ValueError):
        for x in gen():
            calls.append(x)
    assert calls == [1, 2]
    print(chronometer.times)

@pytest.mark.skip
def test_generator_with_exception():
    calls = []

    @chrono(chrono=chronometer)
    def gen():
        yield 1
        yield 2
        raise ValueError('boom')

    with pytest.raises(ValueError):
        for x in gen():
            calls.append(x)

    assert calls == [1, 2]
    print(chronometer.times)

def test_nested_chrono_scopes():
    with Chrono() as outer:
        outer.enter_scope('outer')
        time.sleep(0.005)
        with Chrono() as inner:
            inner.enter_scope('inner')
            time.sleep(0.005)
            inner.exit_scope('inner')
        outer.exit_scope('outer')
    assert 'outer' in outer.times
    assert 'inner' in inner.times

def test_report_dict_bad_order():
    chrono = Chrono()
    with pytest.raises(ValueError):
        chrono.report_dict(order='invalid')

@pytest.mark.noci
def test_chrono_context_manager():
    with Chrono('foo') as c:
        time.sleep(0.01)
    assert 'foo' in c.times
    assert 0.01 <= c.times['foo'][0] < 0.012

@pytest.mark.noci
def test_scope_context_manager():
    c = Chrono()
    with c.scope('foo'):
        time.sleep(0.01)
    assert 'foo' in c.times
    assert 0.01 <= c.times['foo'][0] < 0.012

@pytest.mark.noci
def test_nested_scope_context_manager():
    c = Chrono()
    target = make_nested_calls(c)
    for n in 'foo bar baz'.split():
        assert n in c.times
        assert target[n] <= c.times[n][0] < target[n] + 0.002

chrono_report_expected = """
╭─ Profile of test_chrono (order=total, summary=sum) ─╮
│  total │ active │ scope                             │
│ ╶──────┼────────┼──────────────────────────────╴    │
│    TTT │    AAA │ test_chrono                       │
│    TTT │    AAA │ test_chrono.chrono_deco_func3     │
│    TTT │    AAA │ test_chrono.chrono_deco_func2     │
│    TTT │    AAA │ test_chrono.chrono_deco_func      │
╰─────────────────────────────────────────────────────╯
"""

@pytest.mark.noci
def test_chrono_report():
    chrono = Chrono()
    make_nested_calls(chrono)
    report = chronometer.report(order='total', test=True, printme=False)
    evn.diff(chrono_report_expected, report, strip=True)
    if report.strip() != chrono_report_expected.strip():
        chronometer.report(order='total', printme=True, mintime=0)
        print(report)
    assert report.strip() == chrono_report_expected.strip()

if __name__ == '__main__':
    main()
