import pytest
import evn

def main():
    evn.testing.quicktest(namespace=globals())

@pytest.mark.noci
def test_outermost_scope_name():
    from evn._prelude.run_info import outermost_scope_name
    assert outermost_scope_name() == 'test_run_info', f'outermost scope name {outermost_scope_name()} != test_run_info'

if __name__ == '__main__':
    main()
