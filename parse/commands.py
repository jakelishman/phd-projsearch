"""Contains functions for converting the commands in user input files into lists
of machine-readable lines that can be written out, or converted into full
RunParameters."""

from ..functional import exists, tuples
from . import types
import itertools
import numpy as np

__all__ = ["expand"]

def _sequences_of_length(start, stop=None):
    """_sequence_of_length(start: int, stop: int) -> generator of list of int

    Get all allowable sequences of first-order sidebands (and carrier) which
    have lengths between `start` and `stop` inclusive.  If `stop` is not given,
    then get all sequences of length `start` only.

    All sequences will be unique, and there will be none with two adjacent
    pulses of the same colour."""
    def allowed(orders):
        return not exists(lambda t: t[0] == t[1], tuples(orders, 2))
    def possibles(nsides):
        return filter(allowed, itertools.product([0, -1, 1], repeat = nsides))
    lengths = [start] if stop is None else range(start, stop + 1)
    iter_ = itertools.chain.from_iterable(map(possibles, lengths))
    return map(types.string.sequence, iter_)

# All functions of the form `[parameter]_[command](args)` are input file
# commands, and correspond to a command `![command] arg1 arg2 ...` called in the
# file for the parameter.

def sequence_length(args):
    """!length (start: int) [(stop: int)]

    Generate all allowable sequences with lengths between `start` and `stop`
    inclusive.  If `stop` is not given, then simply give all sequences of length
    `start`."""
    try:
        assert len(args) <= 2
        return _sequences_of_length(*map(int, args))
    except:
        raise TypeError(sequence_length.__doc__)

_known_commands = {
    "sequence": {"length": sequence_length},
}

# For checking whether the inputs are well-formed and interpreting them.
_parsers = {
    "state": types.state,
    "sequence": types.sequence,
    "laser": types.laser,
    "time": types.time,
}

# For converting parsed input back into a form that can be written out to the
# machine-readable file.
_strings = {
    "state": types.string.state,
    "sequence": types.string.sequence,
    "laser": types.string.laser,
    "time": types.string.time,
}

def _make_generator(param, spec):
    """_make_generator(param: str, spec: str) -> generator of str

    Parses the specifier `spec` (which may include user commands) into a
    generator of all of the objects described by `spec` as string.  For example,
        _make_generator("time", "3600") -> [ "3600" ]
    and
        _make_generator("sequence", "!length 1") -> [ "[0]", "[1]", "[-1]" ]
    where the outermost `[]` represent a generator.

    Raises:
    KeyError --
        if the parameter is not known (this should have been checked before).
    ValueError -- if the command is not known.
    TypeError -- if the user has used the command incorrectly."""
    spec = spec.strip()
    if spec[0] != '!':
        # Parse and reconvert to string to check for parse errors and minimise
        # text space needed.
        yield _strings[param](_parsers[param](spec))
    else:
        parts = spec[1:].split()
        knowns = _known_commands[param] if param in _known_commands else {}
        if parts[0] not in knowns:
            raise ValueError("Unknown " + param + " command"
                             + " '!" + parts[0] + "'.")
        yield from knowns[parts[0]](parts[1:])

def expand(param_list):
    """expand(param_list) -> generator of str

    Expand the list of parameters and their specifiers into a generator of
    machine-readable input lines describing all of the specified parameter sets.
    This expands commands in order, so the last element in the list in like the
    inner-most for loop.

    Arguments:
    param_list: iterable of (param: str) * (spec: str) --
        An ordered iterable of pairs for each of the necessary parameters, with
        the parameter name and the specifier for it.

        There should be no duplicates, and everything should be included once.

    Returns:
    generator of str --
        A generator which will return all of the machine-readable lines
        specified by the set of pairs."""
    iters = [ _make_generator(param, spec) for param, spec in param_list ]
    make_statement = lambda tup: param_list[tup[0]][0] + "=" + tup[1]
    make_line = lambda spec: ";".join(map(make_statement, enumerate(spec)))
    return map(make_line, itertools.product(*iters))
