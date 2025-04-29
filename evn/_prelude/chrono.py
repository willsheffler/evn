from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
import signal
import types
import typing as t

import evn
from evn._prelude.make_decorator import make_decorator
from evn._prelude.run_info import outermost_scope_name

@dataclass
class Chrono:
    name: str = 'Chrono'
    verbose: bool = False
    start_time: float = field(default_factory=perf_counter)
    scopestack: list['ChronoScope'] = field(default_factory=list)
    times: dict[str, list] = field(default_factory=dict)
    times_tot: dict[str, list] = field(default_factory=dict)
    report_name_replace: dict[str, str] = field(default_factory=dict)
    run_on_exit: list = field(default_factory=list)
    entered: bool = False
    _pre_checkpoint_name: str | None = None
    stopped: bool = False
    debug: bool = False

    def __post_init__(self):
        self.start()

    def clear(self):
        self.times.clear()
        self.times_tot.clear()
        self.scopestack.clear()
        self.start()
        self.debug = False

    def start(self):
        assert not self.stopped
        self.scopestack.append(ChronoScope(self.name, chrono=self))

    def stop(self):
        """Stop the chrono and store total elapsed time."""
        assert not self.stopped
        self.exit_scope(self.name)
        self.times['total'] = [perf_counter() - self.start_time]
        self.times_tot['total'] = self.times['total']
        self.stopped = True

    def __enter__(self):
        if not self.entered: self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type: print(f'An exception of type {exc_type} occurred: {exc_val}')
        self.stop()

    def scope(self, scopekey) -> t.ContextManager:
        name = self.check_scopekey(scopekey, 'scope')

        @contextmanager
        def cm(chrono=self):
            chrono.enter_scope(name)
            yield
            chrono.exit_scope(name)

        return cm()

    def end_scope(self, scope):
        assert not (self.stopped or scope.stopped)
        # print(scope.name, evn.ident.hash(scope), t)
        time, tottime = scope.final()
        self.times.setdefault(scope.name, []).append(time)
        active_scopes = [s.name for s in self.scopestack]
        if scope.name not in active_scopes:
            self.times_tot.setdefault(scope.name, []).append(tottime)

    def scope_name(self, obj: 'str|object') -> str:
        if isinstance(obj, str): return obj
        if hasattr(obj, '__module__'):
            return f'{obj.__module__}.{obj.__qualname__}'.replace('.<locals>', '')
        return f'{obj.__qualname__}'.replace('.<locals>', '')

    def enter_scope(self, scopekey):
        self._pre_checkpoint_name = ''
        name = self.check_scopekey(scopekey, 'enter_scope')
        if self.scopestack:
            self.scopestack[-1].subscope_begins()
        self.scopestack.append(ChronoScope(name, chrono=self))

    def exit_scope(self, scopekey: str | object, strict: bool = True):
        self._pre_checkpoint_name = ''
        name = self.check_scopekey(scopekey, 'exit_scope')
        if not self.scopestack: raise RuntimeError('Chrono is not running')
        err = f'exiting scope: {name} doesnt match: {self.scopestack[-1].name}'
        if strict: assert self.scopestack[-1].name == name, err
        self.end_scope(self.scopestack.pop())
        if self.scopestack: self.scopestack[-1].subscope_ends()

    def checkpoint(self, scopekey: str | object):
        oldname = self.scopestack[-1].name
        newname = self.check_scopekey(scopekey, 'checkpoint')
        if not self._pre_checkpoint_name: self._pre_checkpoint_name = oldname
        self.scopestack[-1].name = newname
        self.end_scope(self.scopestack.pop())
        self.scopestack.append(ChronoScope(self._pre_checkpoint_name, chrono=self))

    def check_scopekey(self, scopekey, label):
        if self.debug: print(label, scopekey)
        assert not self.stopped
        return self.scope_name(scopekey)

    def elapsed(self) -> float:
        """Return the total elapsed time."""
        return perf_counter() - self.start_time

    def find_times(self, name) -> list:
        return next((v for k, v in self.times.items() if name in k), [])

    def report_dict(self, order='active', summary=sum, mintime=0.0, do_replacements=True):
        """
        Generate a report dictionary of
         times.

        Args:
            order (str): Sorting order ('active' or 'callorder').
            summary (callable): Function to summarize times (e.g., sum, mean).
            mintime (float): Minimum time cutoff for inclusion

        Returns:
            dict: Checkpoint times summary.
        """
        keys = self.times_tot.keys()
        times = evn.dictmap(summary, self.times)
        times_tot = evn.dictmap(summary, self.times_tot)
        report = evn.Bunch({
            k: evn.Bunch(total=times_tot[k], active=times[k])
            for k in keys if order == 'total' and times_tot[k] >= mintime or times[k] >= mintime
        })
        for still_active in reversed(self.scopestack):
            time, tottime = still_active.final(stop=False)
            report[still_active.name] = evn.Bunch(total=tottime, active=time)
        if order == 'active':
            report = dict(sorted(report.items(), key=lambda k: k[1].active, reverse=True))
        elif order == 'total':
            report = dict(sorted(report.items(), key=lambda k: k[1].total, reverse=True))
        elif order == 'callorder':
            report = report
        elif order == 'alphabetical':
            report = dict(sorted(report.items()))
        else:
            raise ValueError(f'Unknown order: {order}')
        if do_replacements and self.report_name_replace:
            for kold in list(report.keys()):
                k = kold
                for old, new in self.report_name_replace.items():
                    k = k.replace(old, new)
                report[k] = report.pop(kold)
        return report

    def report(self,
               order='active',
               summary=sum,
               test=False,
               printme=True,
               mintime=0,
               header='',
               footer='',
               width=None) -> str:
        """
        Print or return a report of
         profile.

        Args:
            order (str): Sorting order ('active', 'total', or 'callorder').
            summary (callable): Function to summarize profile (e.g., sum, mean).
            printme (bool): Whether to print the report.

        Returns:
            str: Report string.
        """
        profile = self.report_dict(order=order, summary=summary, mintime=mintime)
        if test:
            for v in profile.values():
                v.total = 'TTT'
                v.active = 'AAA'
        with evn.capture_stdio() as capture:
            if header: print(header)
            evn.console.print_table(
                profile,
                title=f'Profile of {self.name} (order={order}, summary={summary.__name__})',
                justify='left',
                keylast=True,
                key='scope',
                border=True,
                width=width,
                # overflow='fold',
            )
            if footer: print(footer)
        report = capture.read()
        # report_lines = [f'Chrono Report ({self.name})']
        # report_lines.extend(f'{name}: {time_:.6f}s' for name, time_ in profile.items())
        # report = '\n'.join(report_lines)
        if printme:
            print(report)
        return report

    def report_on_exit(self, header=' ', mintime=0.1, order='active', multiple=False, replace=False):
        if self.run_on_exit and not multiple and replace:
            print('⚠️  Chrono.report_on_exit: replacing previous report function')
            self.run_on_exit.pop()
        elif self.run_on_exit and not multiple: return
        self.run_on_exit.append(lambda: self.report(order=order, mintime=mintime, header=header))
        import atexit
        atexit.register(self.run_on_exit[-1])
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"⚠️  Caught signal {signum}, cleaning up…")
        for func in self.run_on_exit:
            func()
        # Re-raise default handler so program terminates with the correct exit code
        signal.signal(signum, signal.SIG_DFL)
        assert 0, f"Program terminated by signal {signum}"

@dataclass
class ChronoScope:
    name: str
    chrono: Chrono
    start_time: float = field(default_factory=perf_counter)
    sub_start: float = field(default_factory=perf_counter)
    total: float = 0
    subtotal: float = 0
    stopped: bool = False
    debug: bool = False

    def __post_init__(self):
        self.short = self.name.split('.')[-1]
        self.pad = len(self.chrono.scopestack) * '  '
        if self.debug:
            print(f'{self.pad} scope_beg {self.short}')  #, {self.start_time-self.chrono.start_time:7.3f}')

    def final(self, stop=True):
        if self.debug: print(f'{self.pad} scope_end {self.short}, {perf_counter()-self.start_time:7.3f}')
        if self.sub_start < 9e8:
            self.stopped, subtotal = stop, perf_counter() - self.sub_start + self.subtotal
        else:  # subscope still active... must be intermediate report
            subtotal = self.subtotal
        return subtotal, perf_counter() - self.start_time

    def subscope_begins(self):
        if self.debug: print(self.pad, 'subsc_beg', self.short)
        self.subtotal += perf_counter() - self.sub_start
        self.sub_start = 9e9

    def subscope_ends(self):
        if self.debug: print(self.pad, 'subsc_end', self.short)
        self.sub_start = perf_counter()

# print('new chronometer', outermost_scope_name))
evn.chronometer = Chrono(outermost_scope_name())
# evn.chronometer = Chrono('main')

def chrono_scope(name, **kw):
    global chronometer
    chrono = kw.get('chrono', evn.chronometer)
    chrono.scope(name, **kw)

def chrono_enter_scope(name, **kw):
    global chronometer
    chrono = kw.get('chrono', evn.chronometer)
    chrono.enter_scope(name, **kw)

def chrono_exit_scope(name, **kw):
    global chronometer
    chrono = kw.get('chrono', evn.chronometer)
    chrono.exit_scope(name, **kw)

def chrono_checkpoint(name, **kw):
    global chronometer
    chrono = kw.get('chrono', evn.chronometer)
    chrono.checkpoint(name, **kw)

@make_decorator(chrono=evn.chronometer)
def chrono(wrapped=None, *args, chrono: Chrono | None = None, **kw) -> t.Callable:
    assert wrapped
    chrono2: Chrono = kw.get('chrono', chrono)
    chrono2.enter_scope(wrapped)
    result = wrapped(*args, **kw)
    chrono2.exit_scope(wrapped)
    if not isinstance(result, types.GeneratorType):
        return result
    return _generator_proxy(wrapped, result, chrono2)  # type:ignore

def _generator_proxy(gener, wrapped, chrono) -> t.Generator:
    try:
        geniter = iter(gener)
        while True:
            # chrono.enter_scope(wrapped)
            with chrono.scope(wrapped):
                yield next(geniter)
            # chrono.exit_scope(wrapped)
            # yield item
    except StopIteration:
        pass
    finally:
        with chrono.scope(wrapped):
            if hasattr(gener, 'close'):
                gener.close()
