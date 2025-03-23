import os
import nox

nox.options.sessions = ['test_matrix']
# nox.options.sessions = ['test_matrix', 'build']
sesh = dict(python=["3.9", "3.10", "3.11", "3.12", "3.13"] , venv_backend='uv')

def run(session, cmd):
    session.run(*cmd.split())

@nox.session(**sesh)
def test_matrix(session):
    nprocs = min(8, os.cpu_count() or 1)
    if session.posargs and (session.python) != session.posargs[0]:
        session.skip(f"Skipping {session.python} because it's not in posargs {session.posargs}")
    run(session, 'uv venv')
    run(session, 'uv pip install --find-links=wheelhouse evn[dev]')
    if len(session.posargs) > 1:
        files = session.posargs[1:]
        run(session, f'pytest {" ".join(files)}')
    else:
        run(session, f'pytest -n{nprocs} --doctest-modules --pyargs evn')

@nox.session(**sesh)
def build(session):
    session.run(*'uv build .'.split())
