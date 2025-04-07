# test_lazy_dispatch.py
import sys
import types
import pytest

import evn
from evn._prelude.lazy_dispatch import GLOBAL_DISPATCHERS, lazydispatch, LazyDispatcher


class FakeArray:

    def __init__(self, size):
        self.size = size
        self.shape = (size, )


FakeArray.__name__ = 'ndarray'
FakeArray.__qualname__ = 'ndarray'
FakeArray.__module__ = 'numpy'


class FakeTensor:

    def __init__(self, numel):
        self._numel = numel
        self.shape = (numel, )

    def numel(self):
        return self._numel


FakeTensor.__name__ = 'Tensor'
FakeTensor.__qualname__ = 'torch.Tensor'


@pytest.fixture
def fake_numpy_module():
    module = types.ModuleType('numpy')
    module.ndarray = FakeArray
    sys.modules['numpy'] = module
    yield module
    del sys.modules['numpy']


@pytest.fixture
def fake_torch_module():
    module = types.ModuleType('torch')
    module.Tensor = FakeTensor
    sys.modules['torch'] = module
    yield module
    del sys.modules['torch']


def test_dispatch_deco():

    @lazydispatch
    def foo(obj):
        print(obj)

    assert isinstance(foo, LazyDispatcher)


def test_dispatch_deco_nest():

    @lazydispatch(scope='local')
    def foo(obj):
        print(obj)

    assert isinstance(foo, LazyDispatcher)


def test_dispatch_global_registry():
    GLOBAL_DISPATCHERS.clear()

    @lazydispatch(scope='local')
    def describe(obj):
        return 'default'

    @lazydispatch(list, scope='local')
    def describe(obj):
        return 'list'

    assert len(GLOBAL_DISPATCHERS) == 1


def test_dispatchers_match():
    GLOBAL_DISPATCHERS.clear()

    @lazydispatch(scope='local')
    def describe(obj):
        return 'default'

    describe1 = describe
    assert isinstance(describe1, LazyDispatcher)

    @lazydispatch(list, scope='local')
    def describe(obj):
        return 'list'

    describe2 = describe
    assert isinstance(describe2, LazyDispatcher)
    assert describe1 is evn.first(GLOBAL_DISPATCHERS.values())
    assert describe1 is describe2

    assert describe([1, 2]) == 'list'
    assert describe(42) == 'default'


def test_dispatch_default():
    GLOBAL_DISPATCHERS.clear()

    @lazydispatch(scope='local')
    def describe(obj):
        return 'default'

    describe1 = describe

    @lazydispatch(list, scope='local')
    def describe(obj):
        return 'list'

    describe2 = describe
    assert describe1 is describe2

    assert describe([1, 2]) == 'list'
    assert describe(42) == 'default'


def test_lazy_registration_numpy(fake_numpy_module):

    @lazydispatch(scope='local')
    def describe(obj):
        return 'default'

    @lazydispatch('numpy.ndarray', scope='local')
    def describe(obj):
        return f'ndarray({obj.size})'

    arr = fake_numpy_module.ndarray(5)
    assert describe(arr) == 'ndarray(5)'


def test_lazy_registration_torch(fake_torch_module):

    @lazydispatch(scope='local')
    def summary(obj):
        return 'base'

    @lazydispatch('torch.Tensor', scope='local')
    def summary(obj):
        return f'tensor({obj.numel()})'

    t = fake_torch_module.Tensor(12)
    assert summary(t) == 'tensor(12)'


def test_scope_global_allows_shared_name():

    @lazydispatch(scope='global')
    def compute(obj):
        return 'default'

    @lazydispatch('builtins.int', scope='global')
    def compute(obj):
        return 'int'

    assert compute(5) == 'int'
    assert compute('x') == 'default'


def test_scope_local_disambiguation():

    @lazydispatch(scope='local')
    def action(obj):
        return 'default'

    @lazydispatch('builtins.int', scope='local')
    def action(obj):
        return 'int'

    assert action(123) == 'int'
    assert action('hi') == 'default'


def test_unresolved_type_skips():

    @lazydispatch(scope='local')
    def handler(obj):
        return 'base'

    @lazydispatch('ghost.Type', scope='local')
    def handler(obj):
        return 'ghost'

    class Other:
        pass

    assert handler(Other()) == 'base'


def test_missing_dispatcher_errors():
    with pytest.raises(ValueError):

        @lazydispatch('foo.   Bar')
        def nothing(obj):
            return 'fail'

        print(nothing(5))
