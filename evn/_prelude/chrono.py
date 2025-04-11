import types
from time import perf_counter
from dataclasses import dataclass, field

from evn._prelude.lazy_import import lazyimport

np = lazyimport('numpy')
import evn
from evn._prelude.make_decorator import make_decorator

@dataclass
class Chrono:
    name: str = 'Chrono'
    initial_scope: str = 'misc'
    verbose: bool = False
    start_time: float = field(default_factory=perf_counter)
    scopestack: list = field(default_factory=list)
    profile: dict[str, list] = field(default_factory=dict)
    entered: bool = False
    stopped: bool = False

    def __post_init__(self):
        self.start()

    def start(self):
        assert not self.stopped
        self.scopestack.append(TimerScope(self.initial_scope))

    def stop(self):
        """Stop the chrono and store total elapsed time."""
        assert not self.stopped
        self.exit_scope(self.initial_scope)
        self.store_finished_scope(TimerScope('total', 0, self.elapsed()))
        self.stopped = True

    def __enter__(self):
        assert not self.stopped
        if not self.entered: self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert not self.stopped
        if exc_type: print(f'An exception of type {exc_type} occurred: {exc_val}')
        self.stop()
        return False

    def store_finished_scope(self, scope):
        assert not (self.stopped or scope.stopped)
        t = scope.final()
        print(scope.name, evn.ident.hash(scope), t)
        self.profile.setdefault(scope.name, []).append(t)

    def scope_name(self, obj: 'str|object') -> str:
        if isinstance(obj, str): return obj
        return f'{obj.__module__}.{obj.__qualname__}'.replace('.<locals>', '')

    def enter_scope(self, ctxkey):
        assert not self.stopped
        name = self.scope_name(ctxkey)
        if self.scopestack:
            self.scopestack[-1].subscope_begins()
        new = TimerScope(name)
        self.scopestack.append(new)

    def exit_scope(self, ctxkey: 'str|object' = 'timer shutdown'):
        assert not self.stopped
        name = self.scope_name(ctxkey)
        if not self.scopestack: raise RuntimeError('Chrono is not running')
        err = f'exiting scope: {name} mismatches: {self.scopestack[-1].name}'
        assert self.scopestack[-1].name == name, err
        self.store_finished_scope(self.scopestack.pop())
        if self.scopestack: self.scopestack[-1].subscope_ends()

    def elapsed(self) -> float:
        """Return the total elapsed time."""
        return perf_counter() - self.start_time

    def get_checkpoint_data(self, name: str):
        """
        Retrieve
         profile.

        Args:
            name (str): The
             label.

        Returns:
            np.ndarray: Array of
             profile.
        """
        return self.profile.get(name, [])

    def report_dict(self, order='longest', summary=sum):
        """
        Generate a report dictionary of
         profile.

        Args:
            order (str): Sorting order ('longest' or 'callorder').
            summary (callable): Function to summarize profile (e.g., sum, mean).

        Returns:
            dict: Checkpoint profile summary.
        """
        items = self.profile.keys()
        if order == 'longest':
            sorted_items = sorted(items, key=lambda k: self.get_checkpoint_data(k))
        elif order == 'callorder':
            sorted_items = items
        else:
            raise ValueError(f'Unknown order: {order}')
        return {k: summary(self.get_checkpoint_data(k)) for k in sorted_items}

    def report(self, order='longest', summary=sum, printme=True) -> str:
        """
        Print or return a report of
         profile.

        Args:
            order (str): Sorting order ('longest' or 'callorder').
            summary (callable): Function to summarize profile (e.g., sum, mean).
            printme (bool): Whether to print the report.

        Returns:
            str: Report string.
        """
        profile = self.report_dict(order=order, summary=summary)
        report_lines = [f'Chrono Report ({self.name})']
        report_lines.extend(f'{name}: {time_:.6f}s' for name, time_ in profile.items())
        report = '\n'.join(report_lines)
        if printme:
            print(report)
        return report

@dataclass
class TimerScope:
    name: str
    start_time: float = field(default_factory=perf_counter)
    subtotal: float = 0
    stopped: bool = False

    def final(self):
        # ic(perf_counter(), self.start_time, self.subtotal)
        self.stopped, elapsed = True, perf_counter() - self.start_time + self.subtotal
        return elapsed

    def subscope_begins(self):
        self.subtotal += perf_counter() - self.start_time
        self.start_time = 0

    def subscope_ends(self):
        self.start = perf_counter()

evn.chrono_main = Chrono('main')

def chrono_enter_scope(name, **kw):
    global chrono_main
    t = kw.get('chrono', evn.chrono_main)
    t.enter_scope(name, **kw)

def chrono_exit_scope(name, **kw):
    global chrono_main
    t = kw.get('chrono', evn.chrono_main)
    t.exit_scope(name, **kw)

@make_decorator(chrono=evn.chrono_main)
def chrono(wrapped, *args, chrono=None, **kw):
    timer: Chrono = kw.get('chrono', chrono)
    timer.enter_scope(wrapped)
    result = wrapped(*args, **kw)
    timer.exit_scope(wrapped)
    if not isinstance(result, types.GeneratorType):
        return result

    def generator_proxy():
        try:
            geniter = iter(result)
            while True:
                timer.enter_scope(wrapped)
                item = next(geniter)
                timer.exit_scope(wrapped)
                yield item
        except StopIteration:
            pass
        finally:
            timer.exit_scope(wrapped)
            if hasattr(result, 'close'):
                result.close()

    return generator_proxy()
