import statistics
import pytest
import time
import random
from evn._prelude.chrono import Chrono, chrono, TimerContext
# from evn.dynamic_float_array import DynamicFloatArray

import evn

orig_name = __name__
__name__ = 'test_chrono'

config_test = evn.Bunch(
    re_only=[
        #
    ],
    re_exclude=[
        #
    ],
)


def main():
    evn.testing.maintest(
        namespace=globals(),
        config=config_test,
        verbose=1,
        check_xfail=False,
        chrono=False,
    )


class ChronoTest:

    def __init__(self):
        self.runtime = {
            'method1': [],
            'method2': [],
            'recursive': [],
            'generator': []
        }

    @chrono
    def method1(self):
        start = time.perf_counter()
        time.sleep(0.01)  # random.uniform(0.01, 0.03))
        print(self)
        self.runtime['method1'].append(time.perf_counter() - start)
        self.method2()
        start = time.perf_counter()
        time.sleep(0.01)  # random.uniform(0.01, 0.03))
        self.runtime['method1'].append(time.perf_counter() - start)

    @chrono
    def method2(self):
        start = time.perf_counter()
        time.sleep(0.01)  # random.uniform(0.01, 0.03))
        self.runtime['method2'].append(time.perf_counter() - start)
        self.recursive(random.randint(1, 3))
        start = time.perf_counter()
        time.sleep(0.01)  # random.uniform(0.01, 0.03))
        self.runtime['method2'].append(time.perf_counter() - start)

    @chrono
    def recursive(self, depth):
        if not depth:
            return
        start = time.perf_counter()
        time.sleep(0.01)  # random.uniform(0.01, 0.03))
        self.runtime['recursive'].append(time.perf_counter() - start)
        self.recursive(depth - 1)
        start = time.perf_counter()
        time.sleep(0.01)  # random.uniform(0.01, 0.03))
        self.runtime['recursive'].append(time.perf_counter() - start)

    @chrono
    def generator(self):
        start = time.perf_counter()
        time.sleep(0.01)  # random.uniform(0.01, 0.03))
        self.runtime['generator'].append(time.perf_counter() - start)
        for i in range(3):
            start = time.perf_counter()
            time.sleep(0.01)  # random.uniform(0.01, 0.03))
            self.runtime['generator'].append(time.perf_counter() - start)
            yield i
            start = time.perf_counter()
            time.sleep(0.01)  # random.uniform(0.01, 0.03))
            self.runtime['generator'].append(time.perf_counter() - start)


def test_chrono_nesting():
    instance = ChronoTest()
    instance.method1()
    assert list(instance.generator()) == [0, 1, 2]
    report = evn.chrono_main.report_dict()
    print(report.keys())
    for method in 'method1 method2 recursive generator'.split():
        try:
            recorded_time = sum(instance.runtime[method])
            print(report.keys())
            chrono_time = report[f'test_chrono.ChronoTest.{method}']
            err = f'Mismatch in {method}, internal: {recorded_time} vs chrono: {chrono_time}'
            assert abs(recorded_time - chrono_time) < 0.005, err
        except KeyError:
            print(f'missing key {method}')
            assert 0
    assert evn.chrono_main.contextstack[-1].name == 'misc'


def hypothesis_test_chrono_class():
    from hypothesis import given, strategies as st

    @given(
        st.lists(
            st.tuples(st.sampled_from(['method1', 'method2', 'recursive']),
                      st.integers(1, 3)),
            min_size=5,
            max_size=10,
        ))
    def run_test(call_sequence):
        evn.global_chrono = Chrono(start=True,
                                   use_cython=random.choice([True, False]))
        instance = TestClass()

        for method, depth in call_sequence:
            if method == 'recursive':
                instance.recursive(depth)
            else:
                getattr(instance, method)()

        evn.global_chrono.stop()
        report = evn.global_chrono.report_dict()
        for method in instance.runtime:
            recorded_time = sum(instance.runtime[method])
            chrono_time = report.get(
                f'test_chrono_class.<locals>.TestClass.{method}', 0)
            assert (
                abs(recorded_time - chrono_time) < 0.01
            ), f'Mismatch in {method}: {recorded_time} vs {chrono_time}'

    run_test()


def test_chrono_func():
    timer = Chrono()

    @chrono(chrono=timer)
    def foo():
        time.sleep(0.001)

    foo()
    assert 'test_chrono.test_chrono_func.foo' in timer.profile
    assert len(timer.profile['test_chrono.test_chrono_func.foo']) == 1
    print(timer.profile['test_chrono.test_chrono_func.foo'])
    assert sum(timer.profile['test_chrono.test_chrono_func.foo']) >= 0.001


def test_context():
    with Chrono() as t:
        t.enter_context('baz')
        t.enter_context('bar')
        t.enter_context('foo')
        t.exit_context('foo')
        t.exit_context('bar')
        t.exit_context('baz')
    assert 'foo' in t.profile
    assert 'bar' in t.profile
    assert 'baz' in t.profile


def allclose(a, b, atol):
    if isinstance(a, float):
        return abs(a - b) < atol
    for x, y in zip(a, b):
        if abs(a - b) > atol:
            return False
    return True


@pytest.mark.skip
def test_chrono():
    with Chrono() as chrono:
        time.sleep(0.02)
        chrono.exit_context('foo')
        time.sleep(0.06)
        chrono.exit_context('bar')
        time.sleep(0.04)
        chrono.exit_context('baz')

    times = chrono.report_dict()
    assert allclose(times['foo'], 0.02, atol=0.05)
    assert allclose(times['bar'], 0.06, atol=0.05)
    assert allclose(times['baz'], 0.04, atol=0.05)

    times = chrono.report_dict(order='longest')
    assert list(times.keys()) == ['total', 'bar', 'baz', 'foo']

    times = chrono.report_dict(order='callorder')
    assert list(times.keys()) == ['foo', 'bar', 'baz', 'total']

    with pytest.raises(ValueError):
        chrono.report_dict(order='oarenstoiaen')


def test_summary():
    with Chrono() as chrono:
        chrono.enter_context('foo')
        time.sleep(0.01)
        chrono.exit_context('foo')
        chrono.enter_context('foo')
        time.sleep(0.03)
        chrono.exit_context('foo')
        chrono.enter_context('foo')
        time.sleep(0.02)
        chrono.exit_context('foo')
    times = chrono.report_dict(summary=sum)
    assert allclose(times['foo'], 0.06, atol=0.02)

    times = chrono.report_dict(summary=statistics.mean)
    assert allclose(times['foo'], 0.02, atol=0.01)

    times = chrono.report_dict(summary=min)
    assert allclose(times['foo'], 0.01, atol=0.01)

    with pytest.raises(TypeError):
        chrono.report(summary='foo')

    with pytest.raises(TypeError):
        chrono.report(summary=1)


def test_chrono_stop_behavior():
    chrono = Chrono()
    chrono.enter_context('foo')
    chrono.exit_context('foo')
    chrono.stop()
    assert chrono.stopped
    with pytest.raises(AssertionError):
        chrono.enter_context('bar')
    with pytest.raises(AssertionError):
        chrono.store_checkpoint(TimerContext('baz'))


def test_context_mismatch():
    chrono = Chrono()
    chrono.enter_context('foo')
    with pytest.raises(
            AssertionError,
            match='stored context: foo does not match exit context: bar'):
        chrono.exit_context('bar')


def test_context_name_from_object():
    chrono = Chrono()

    class Dummy:
        pass

    name = chrono.context_name(Dummy)
    assert isinstance(name, str)
    assert 'Dummy' in name


def test_get_checkpoint_data_missing():
    chrono = Chrono()
    assert chrono.get_checkpoint_data('not_there') == []


def test_report_string_return():
    with Chrono() as chrono:
        chrono.enter_context('foo')
        time.sleep(0.01)
        chrono.exit_context('foo')
    report = chrono.report(printme=False)
    assert isinstance(report, str)
    assert 'foo' in report


def test_generator_with_exception():
    calls = []

    @chrono
    def gen():
        yield 1
        yield 2
        raise ValueError('boom')

    with pytest.raises(ValueError):
        for x in gen():
            calls.append(x)

    assert calls == [1, 2]
    assert 'test_chrono.test_generator_with_exception.gen' in evn.chrono_main.profile


def test_nested_chrono_contexts():
    with Chrono() as outer:
        outer.enter_context('outer')
        time.sleep(0.005)
        with Chrono() as inner:
            inner.enter_context('inner')
            time.sleep(0.005)
            inner.exit_context('inner')
        outer.exit_context('outer')
    assert 'outer' in outer.profile
    assert 'inner' in inner.profile


def test_report_dict_bad_order():
    chrono = Chrono()
    with pytest.raises(ValueError):
        chrono.report_dict(order='invalid')


if orig_name == '__main__':
    main()
