import os
import glob
import evn

def main():
    evn.testing.quicktest(namespace=globals())

def test_nocontext():
    with evn.dev.nocontext() as foo:
        assert foo is None

def test_cast():
    # cast(cls, self)
    ...

def test_redirect():
    # redirect(stdout=<_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>, stderr=<_io.TextIOWrapper name='<stderr>' mode='w' encoding='utf-8'>)
    ...

def test_cd():
    prev = os.getcwd()
    with evn.dev.cd('/'):
        assert os.getcwd() == '/'
    assert os.getcwd() == prev

def test_trace_prints():
    with evn.capture_stdio() as printed:
        with evn.trace_writes_to_stdout() as trace:
            print('76125455762317357825346521683745')
    log = ''.join(trace.log)
    out = printed.read()
    for x in (log, out):
        assert '76125455762317357825346521683745' in x
        assert 'test_trace_prints' in x
        assert 'test_contexts.py' in x

def test_capture_asserts():
    with evn.dev.capture_asserts() as errors:
        assert 1, 'true'
        assert 0, 'foo'
        assert 0, 'bar'
    assert errors
    assert len(errors) == 1
    # assert errors[0] == AssertionError('foo')

if __name__ == '__main__':
    main()
