import unittest
import statistics
import pytest
import time
import random
from evn._prelude.chrono import Chrono, chrono
# from evn.dynamic_float_array import DynamicFloatArray

import evn

config_test = evn.Bunch(
    re_only=[
        #
    ],
    re_exclude=[
        #
    ],
)

def main():
    evn.tests.maintest(
        namespace=globals(),
        config=config_test,
        verbose=1,
        check_xfail=False,
        chrono=False,
    )

class TestClass(unittest.TestCase):

    def setUp(self):
        self.runtime = {"method1": 0, "method2": 0, "recursive": 0, "generator": 0}

    @chrono
    def method1(self):
        start = time.perf_counter()
        time.sleep(random.uniform(0.01, 0.03))
        print(self)
        self.runtime["method1"] += time.perf_counter() - start
        self.method2
        start = time.perf_counter()
        time.sleep(random.uniform(0.01, 0.03))
        self.runtime["method1"] += time.perf_counter() - start

    @chrono
    def method2(self):
        start = time.perf_counter()
        time.sleep(random.uniform(0.01, 0.03))
        self.runtime["method2"] += time.perf_counter() - start
        self.recursive(random.randint(1, 3))
        start = time.perf_counter()
        time.sleep(random.uniform(0.01, 0.03))
        self.runtime["method2"] += time.perf_counter() - start

    @chrono
    def recursive(self, depth):
        if not depth: return
        start = time.perf_counter()
        time.sleep(random.uniform(0.01, 0.03))
        self.runtime["method2"] += time.perf_counter() - start
        self.recursive(depth - 1)
        start = time.perf_counter()
        time.sleep(random.uniform(0.01, 0.03))
        self.runtime["method2"] += time.perf_counter() - start

    @chrono
    def generator(self):
        start = time.perf_counter()
        time.sleep(random.uniform(0.01, 0.03))
        self.runtime["method2"] += time.perf_counter() - start
        for i in range(3):
            start = time.perf_counter()
            time.sleep(random.uniform(0.01, 0.03))
            self.runtime["method2"] += time.perf_counter() - start
            yield i
            start = time.perf_counter()
            time.sleep(random.uniform(0.01, 0.03))
            self.runtime["method2"] += time.perf_counter() - start

@pytest.mark.xfail
def test_chrono_class():
    evn.global_chrono = Chrono()
    instance = TestClass()

    instance.method1()
    instance.method2()
    list(instance.generator())

    report = evn.global_chrono.report_dict()

    for method in instance.runtime:
        recorded_time = sum(instance.runtime[method])
        chrono_time = report.get(f"test_chrono_class.<locals>.TestClass.{method}", 0)
        assert abs(recorded_time -
                   chrono_time) < 0.01, f"Mismatch in {method}: {recorded_time} vs {chrono_time}"

def hypothesis_test_chrono_class():
    from hypothesis import given, strategies as st

    @given(
        st.lists(st.tuples(st.sampled_from(["method1", "method2", "recursive"]), st.integers(1, 3)),
                 min_size=5,
                 max_size=10))
    def run_test(call_sequence):
        evn.global_chrono = Chrono(start=True, use_cython=random.choice([True, False]))
        instance = TestClass()

        for method, depth in call_sequence:
            if method == "recursive":
                instance.recursive(depth)
            else:
                getattr(instance, method)()

        evn.global_chrono.stop()
        report = evn.global_chrono.report_dict()
        for method in instance.runtime:
            recorded_time = sum(instance.runtime[method])
            chrono_time = report.get(f"test_chrono_class.<locals>.TestClass.{method}", 0)
            assert abs(recorded_time -
                       chrono_time) < 0.01, f"Mismatch in {method}: {recorded_time} vs {chrono_time}"

    run_test()

def test_chrono_func():

    @chrono
    def foo():
        time.sleep(0.001)

    foo()
    print(evn.global_chrono.profile)
    assert 'test_chrono_func.<locals>.foo' in evn.global_chrono.profile

def test_context():
    with Chrono() as t:
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
        chrono.exit_context("foo")
        time.sleep(0.06)
        chrono.exit_context("bar")
        time.sleep(0.04)
        chrono.exit_context("baz")

    times = chrono.report_dict()
    assert allclose(times["foo"], 0.02, atol=0.05)
    assert allclose(times["bar"], 0.06, atol=0.05)
    assert allclose(times["baz"], 0.04, atol=0.05)

    times = chrono.report_dict(order="longest")
    assert list(times.keys()) == ["total", "bar", "baz", "foo"]

    times = chrono.report_dict(order="callorder")
    assert list(times.keys()) == ["foo", "bar", "baz", "total"]

    with pytest.raises(ValueError):
        chrono.report_dict(order="oarenstoiaen")

def aaaa(chrono=None):
    exit_context(chrono=chrono, funcbegin=True)
    time.sleep(0.2)
    exit_context(chrono=chrono)

##@chrono
def bbbb(**kw):
    time.sleep(0.2)

    t = Chrono()
    aaaa(t)
    areport = t.report(printme=False)

    t = Chrono()
    kw = evn.Bunch(chrono=t)
    exit_context('label', chrono=t)
    bbbb(**kw)
    breport = t.report(printme=False)

    print(areport)
    print(breport.replace("bbbb", "aaaa"))
    # print(breport.replace('bbbb', 'aaaa'))
    # assert areport.strip() == breport.replace('bbbb', 'aaaa').strip()

@pytest.mark.skip
def test_summary():
    with Chrono() as chrono:
        time.sleep(0.01)
        chrono.exit_context("foo")
        time.sleep(0.03)
        chrono.exit_context("foo")
        time.sleep(0.02)
        chrono.exit_context("foo")
    times = chrono.report_dict(summary=sum)
    assert allclose(times["foo"], 0.06, atol=0.02)

    times = chrono.report_dict(summary=statistics.mean)
    assert allclose(times["foo"], 0.02, atol=0.01)

    times = chrono.report_dict(summary="mean")
    assert allclose(times["foo"], 0.02, atol=0.01)

    times = chrono.report_dict(summary="min")
    assert allclose(times["foo"], 0.01, atol=0.01)

    with pytest.raises(ValueError):
        chrono.report(summary="foo")

    with pytest.raises(ValueError):
        chrono.report(summary=1)

def test_chrono_interjection():
    with Chrono() as chrono:
        chrono.exit_context("bar")
        chrono.exit_context()
        chrono.exit_context("baz")
        chrono.exit_context("bar")
        chrono.exit_context("foo")
    assert set(chrono.profile) == {'foo', 'bar', 'baz'}
    assert len(chrono.profile['foo']) == 1
    assert len(chrono.profile['bar']) == 3
    assert len(chrono.profile['baz']) == 1

def test_chrono_interjection_keyword():
    with Chrono() as chrono:
        chrono.exit_context("foo")
        chrono.exit_context(interject=True)
        chrono.exit_context("baz")
        chrono.exit_context("bar")
        chrono.exit_context("foo")

    assert set(chrono.profile) == {'foo', 'bar', 'baz'}
    assert len(chrono.profile['foo']) == 2
    assert len(chrono.profile['bar']) == 2
    assert len(chrono.profile['baz']) == 1

if __name__ == '__main__':
    main()
