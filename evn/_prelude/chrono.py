import types
from time import perf_counter
from dataclasses import dataclass, field

from evn._prelude.lazy_import import lazyimport
from evn._prelude.inspect import trace

np = lazyimport('numpy')
import evn
from evn._prelude.make_decorator import make_decorator

@dataclass(slots=True)
class Chrono:
    name: str = "Chrono"
    initial_context: str = 'misc'
    verbose: bool = False
    start_time: float = field(default_factory=perf_counter)
    contextstack: list = field(default_factory=list)
    profile: dict[str, list] = field(default_factory=dict)
    entered: bool = False
    stopped: bool = False

    def __post_init__(self):
        self.start()

    def start(self):
        assert not self.stopped
        self.contextstack.append(TimerContext(self.initial_context))

    def stop(self):
        """Stop the chrono and store total elapsed time."""
        assert not self.stopped
        self.exit_context(self.initial_context)
        self.store_checkpoint(TimerContext("total", 0, self.elapsed()))
        self.stopped = True

    def __enter__(self):
        assert not self.stopped
        if not self.entered: self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert not self.stopped
        if exc_type:
            print(f"An exception of type {exc_type} occurred: {exc_val}")
        self.stop()
        return False

    @trace
    def store_checkpoint(self, context):
        assert not self.stopped
        self.profile.setdefault(context.name, []).append(context.final())

    def context_name(self, obj: 'str|object') -> str:
        if isinstance(obj, str): return obj
        return f'{obj.__module__}.{obj.__qualname__}'.replace('.<locals>', '')

    @trace
    def enter_context(self, ctx):
        assert not self.stopped
        name = self.context_name(ctx)
        if self.contextstack: self.contextstack[-1].subcontext_begins()
        self.contextstack.append(TimerContext(name))
        print('enter_context', self.contextstack[-1].name, len(self.contextstack))

    @trace
    def exit_context(self, ctx: 'str|object' = 'timer shutdown'):
        assert not self.stopped
        name = self.context_name(ctx)
        if not self.contextstack: raise RuntimeError("Chrono is not running")
        err = f'stored context: {self.contextstack[-1].name} does not match exit context: {name}'
        print(' exit_context', self.contextstack[-1].name, len(self.contextstack)-1)
        assert self.contextstack[-1].name == name, err
        self.store_checkpoint(self.contextstack.pop())
        if self.contextstack: self.contextstack[-1].subcontext_ends()

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

    def report_dict(self, order="longest", summary=sum):
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
        if order == "longest":
            sorted_items = sorted(items, key=lambda k: self.get_checkpoint_data(k))
        elif order == "callorder":
            sorted_items = items
        else:
            raise ValueError(f"Unknown order: {order}")
        return {k: summary(self.get_checkpoint_data(k)) for k in sorted_items}

    def report(self, order="longest", summary=sum, printme=True) -> str:
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
        report_lines = [f"Chrono Report ({self.name})"]
        report_lines.extend(f"{name}: {time_:.6f}s" for name, time_ in profile.items())
        report = "\n".join(report_lines)
        if printme: print(report)
        return report

@dataclass(slots=True)
class TimerContext:
    name: str
    start: float = field(default_factory=perf_counter)
    subtotal: float = 0

    def final(self):
        self.start, elapsed = None, perf_counter() - self.start + self.subtotal
        return elapsed

    @trace
    def subcontext_begins(self):
        self.subtotal += perf_counter() - self.start
        self.start = 0

    @trace
    def subcontext_ends(self):
        self.start = perf_counter()

evn.chrono_main = Chrono('main')

def chrono_enter_context(name, **kw):
    global chrono_main
    t = kw.get("chrono", evn.chrono_main)
    t.enter_context(name, **kw)

def chrono_exit_context(name, **kw):
    global chrono_main
    t = kw.get("chrono", evn.chrono_main)
    t.exit_context(name, **kw)

@make_decorator(chrono=evn.chrono_main)
def chrono(wrapped, args, kw, chrono=None):
    timer: Chrono = kw.get('chrono', chrono)
    timer.enter_context(wrapped)
    result = wrapped(*args, **kw)
    timer.exit_context(wrapped)
    if not isinstance(result, types.GeneratorType):
        return result
    def generator_proxy():
        try:
            geniter = iter(result)
            while True:
                timer.enter_context(wrapped)
                item = next(geniter)
                timer.exit_context(wrapped)
                yield item
        except StopIteration:
            pass
        finally:
            timer.exit_context(wrapped)
            if hasattr(result, 'close'):
                result.close()
    return generator_proxy()
