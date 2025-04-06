import inspect
from time import perf_counter
from dataclasses import dataclass, field
from typing import Union
import wrapt
from evn._prelude.lazy_import import lazyimport
from evn._prelude.inspect import trace
np = lazyimport('numpy')
import evn

@dataclass(slots=True)
class Chrono:
    name: str = "Chrono"
    initial_context: str = 'chrono startup'
    verbose: bool = False
    start: Union[float, None] = field(default_factory=perf_counter)
    contextstack: list = field(default_factory=list)
    profile: dict[str, list] = field(default_factory=dict)

    def stop(self, name='stop'):
        """Stop the chrono and store total elapsed time."""
        if self.start is not None:
            total_elapsed = perf_counter() - self.start
            self.exit_context(name)
            self.store_checkpoint("total", total_elapsed)
            self.start = None

    def __enter__(self):
        self.contextstack.append(TimerContext(self.initial_context))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(f"An exception of type {exc_type} occurred: {exc_val}")
        self.stop()
        return False

    @trace
    def store_checkpoint(self, context):
        self.profile.setdefault(context.name, []).append(context.total)

    def enter_context(self, name):
        if self.contextstack: self.contextstack[-1].subcontext_begins()
        self.contextstack.append(TimerContext(name))

    def exit_context(self, name: str = 'timer shutdown', interject: bool = False):
        if not self.contextstack: raise RuntimeError("Chrono is not running")
        assert self.contextstack[-1].name == name
        self.store_checkpoint(self.contextstack.pop())
        if self.contextstack[-1]: self.contextstack[-1].subcontext_ends()
        return self

    def elapsed(self) -> float:
        """Return the total elapsed time."""
        return perf_counter() - self.start

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
        return np.array(self.profile.get(name, []), dtype=np.float32)

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
            sorted_items = sorted(items, key=lambda k: -summary(self.get_checkpoint_data(k)))
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
        report_lines = [f"Chrono Report ({self.name}) using {self.storage_type}"]
        for name, time_ in profile.items():
            report_lines.append(f"{name}: {time_:.6f}s")
        report = "\n".join(report_lines)
        if printme:
            print(report)
        return report

    @property
    def total(self) -> float:
        """Return total recorded time."""
        return self.get_checkpoint_data("total").sum()

@dataclass(slots=True)
class TimerContext:
    name: str
    start: float = field(default_factory=perf_counter)
    total: float = 0
    def subcontext_begins(self):
        self.total += perf_counter() - self.start
        self.start = 0
    def subcontext_ends(self):
        self.start = perf_counter()

evn.chrono_main = Chrono('main')


@wrapt.decorator()
def chrono(wrapped, instance, args, kw):
    if instance is None and inspect.isclass(wrapped):
        for name, method in vars(wrapped).items():
            if callable(method) and not name.startswith("__"):
                setattr(wrapped, name, chrono(method, **kw))
        return wrapped
    timer = kw.get('timer', evn.chrono_main)
    name = f'{wrapped.__module__}.{wrapped.__name__}'
    timer.enter_context(name)
    result = wrapped(*args, **kw)
    timer.exit_context(name)
    return result

def enter_context(name, **kw):
    global chrono_main
    t = kw.get("timer", evn.chrono_main)
    t.enter_context(name, **kw)

def exit_context(name, **kw):
    global chrono_main
    t = kw.get("timer", evn.chrono_main)
    t.exit_context(name, **kw)
