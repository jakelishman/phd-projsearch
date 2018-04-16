from . import parse
from . import run
from .functional import compose
import ast
import numpy as np
import iontools as it

class ResultSet:
    """Struct for holding a set of results."""
    def __init__(self, run_parameters, infidelity, parameters, success):
        self.run_parameters = run_parameters
        self.infidelity = infidelity
        self.parameters = parameters
        self.success = success

def from_output_file(file_name):
    """from_output_file(file_name: str) -> generator of ResultSet

    Read all the ResultSets from a given file."""
    with open(file_name, "r") as file:
        statements = parse.key_value_statements(file)
        run_parameters = list(parse.next_run_parameters(statements))
        if len(run_parameters) != 1:
            raise ValueError("Found a user input version of the RunParameters."
                             + "  This function should only be run on results.")
        run_parameters = run_parameters[0]
        needed = set(["infidelity", "parameters", "success"])
        for set_ in parse.key_value_sets(needed, statements):
            dict_ = dict(set_)
            for key, val in dict_.items():
                dict_[key] = ast.literal_eval(val)
            yield ResultSet(run_parameters=run_parameters, **dict_)

def _all_traces(states, sequence, parameters, magnitude):
    """Return an iterator which gives the `Sequence.trace` for each different
    starting state."""
    ns = states[0].dims[0][1]
    def mapping(state):
        trace = sequence.trace(parameters, state)
        mod = abs if magnitude else lambda x: x
        return np.array([ list(map(mod, el.full().reshape((2 * ns,))))\
                          for el in trace ])
    return map(mapping, states)

def _remove_unused_motional_states(trace):
    """Remove any motional levels from the trace that are never populated."""
    trace = np.transpose(trace, (1, 0)) #[el, pulse]
    ns = trace.shape[0] // 2
    maxn_e = max(filter(lambda t: any(t[1]), enumerate(trace[:ns])))[0]
    maxn_g = max(filter(lambda t: any(t[1]), enumerate(trace[ns:])))[0]
    maxn = max(maxn_e, maxn_g)
    return np.concatenate((trace[:maxn+1], trace[ns:ns+maxn+1])).T

def _format_complex(j, atol):
    """Get a pretty-printed string version of a complex number."""
    if abs(j) < atol:
        return "0"
    elif abs(j.real) < atol:
        return "{:.8g}i".format(j.imag)
    elif abs(j.imag) < atol:
        return "{:.8g}".format(j.real)
    else:
        return "{:.8g} {} {:.8g}i".format(j.real,
                                           "+" if j.imag >= 0 else "-",
                                           abs(j.imag))

def _convert_to_strings(atol):
    """Convert the result of a `Sequence.trace` so each element is a string."""
    return lambda trace:\
        np.array([_format_complex(x, atol) for x in trace.flat])\
          .reshape(trace.shape)

def _prepend_ket_names(trace):
    """Add a column with the names of the relevant kets to the start."""
    ns = trace.shape[1] // 2
    kets = [ "|{}{}>".format(x, n) for x in [ "e", "g" ] for n in range(ns) ]
    string_size = int(trace.dtype.str.lstrip("<>Uu"))
    ket_size = len("|e{}>".format(ns - 1))
    if ket_size > string_size:
        trace = trace.astype("<U{}".format(ket_size))
    return np.insert(trace, 0, kets, axis = 0)

def _prepend_pulse_names(sequence):
    """Assuming the ket names have already been prepended, insert a heading row
    into the array with the names of the pulses."""
    names = {0: "carrier", 1: "blue", -1: "red"}
    headings = ["", "start"]\
               + list(map(lambda x: names[x.order], sequence.pulses))
    def prepender(trace):
        return np.insert(trace, 0, headings, axis=1)
    return prepender

def _left_pad(trace):
    """Right-align all the elements of each column, so a column is the same
    width all the way down."""
    columns = []
    for column in trace:
        column_max = 0
        for row in column:
            column_max = max(column_max, len(row))
        columns.append([row.rjust(column_max) for row in column])
    return np.array(columns)

def _insert_heading_separator(trace):
    """Insert the row which separates the heading row from the data."""
    mapping = lambda x: "\u253c" if x == "\u2502" else "\u2500"
    sep = "".join(map(mapping, trace[0]))
    return np.array([ trace[0], sep ] + list(trace[1:]))

def _interleave(trace):
    """Interleave the ket rows so they go "|e0>, |g0>, |e1>, ..." instead of
    doing all the "|e>" kets followed by all the "|g>" kets."""
    ns = (trace.shape[0] // 2) - 1
    order = [0, 1] + [2 + n + x * ns for n in range(ns) for x in range(2)]
    return trace[order]

def trace(results, magnitude=False, interleave=False, add_states=[], tol=5e-10):
    """trace(results, magnitude, interleave, add_states) -> iter of str

    Return an iterator of strings which shows a trace of the effects of the
    found pulse sequence on the target state and the other optimised states.

    Arguments:
    results: ResultSet -- the set of results to use
    magnitude: optional bool --
        If True, only show the magnitude of population in each ket at each
        stage, rather than the full magnitude*phase.
    interleave: optional bool --
        If True, display kets in the order [|e0>, |g0>, |e1>, |g1>, ...] rather
        than [|e0>, |e1>, ..., |g0>, |g1>, ...].
    add_states: optional list of dict --
        A list of state specifiers to trace the same sequence for.  These will
        be appended to the automatically included states.
    tol: float -- The tolerance for displaying coefficients as zero."""
    states, sequence = run._prepare_parameters(results.run_parameters)
    ns = states[0].dims[0][1]
    states = np.append(states, [it.state.create(x, ns) for x in add_states])
    traces = _all_traces(states, sequence, results.parameters, magnitude)
    # `traces` now in [ start_state, pulse, ket ] order
    pipeline = compose(
        _remove_unused_motional_states,
        _convert_to_strings(tol),
        _prepend_ket_names,
        _prepend_pulse_names(sequence),
        _left_pad,
        lambda tr: np.array([" \u2502 ".join(l) for l in np.transpose(tr)]),
        _insert_heading_separator,
        _interleave if interleave else lambda trace: trace,
        lambda trace: "\n".join(trace))
    return map(pipeline, traces)
