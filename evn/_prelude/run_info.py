from pathlib import Path
import inspect

def outermost_scope_name() -> str:
    outermost = '__main__'
    for frameinfo in reversed(inspect.stack()):
        if '__file__' not in frameinfo.frame.f_globals: continue
        outermost = Path(frameinfo.frame.f_globals['__file__']).stem
        if outermost[0] == '_' or outermost in ('runpy', 'main', 'runner', 'python', 'doctest', 'pathlib', 'pytest', 'chrono', '_bootstrap', 'ninja_import'):
            continue
        break
    return outermost
