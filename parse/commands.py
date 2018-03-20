from ..functional import exists, tuples
from . import types
import itertools
import numpy as np

__all__ = ["expand"]

def _all_sequences(start=1, stop=None):
    def allowed(orders):
        return not exists(lambda t: t[0] == t[1], tuples(orders, 2))
    def possibles(nsides):
        return filter(allowed, itertools.product([0, -1, 1], repeat = nsides))
    lengths = [start] if stop is None else range(start, stop + 1)
    iter_ = itertools.chain.from_iterable(map(possibles, lengths))
    return map(types.from_sequence, iter_)

def sequence_length(args):
    try:
        assert len(args) <= 2
        return _all_sequences(*map(int, args))
    except:
        raise TypeError("For sequences, '!length [start [stop]]' is the usage.")

_known_commands = {
    "sequence": {"length": sequence_length},
}

_parsers = {
    "state": types.to_state,
    "sequence": types.to_sequence,
    "laser": types.to_laser,
    "time": types.to_time,
}

_to_strings = {
    "state": types.from_state,
    "sequence": types.from_sequence,
    "laser": types.from_laser,
    "time": types.from_time,
}

def _make_generator(param, spec):
    spec = spec.strip()
    if spec[0] != '!':
        # Parse and reconvert to string to check for parse errors and minimise
        # text space needed.
        yield _to_strings[param](_parsers[param](spec))
    else:
        parts = spec[1:].split()
        knowns = _known_commands[param] if param in _known_commands else {}
        if parts[0] not in knowns:
            raise ValueError("Unknown " + param + " command"
                             + " '!" + parts[0] + "'.")
        yield from knowns[parts[0]](parts[1:])

def expand(dict_, order):
    iters = map(lambda pair: _make_generator(*pair), dict_.items())
    make_statement = lambda tup: order[tup[0]] + "=" + tup[1]
    make_line = lambda spec: ";".join(map(make_statement, enumerate(spec)))
    return map(make_line, itertools.product(*iters))
