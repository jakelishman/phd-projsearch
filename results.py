from . import parse
from . import run
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

def trace(results, magnitude=False, interleave=False, add_states=[]):
    """trace(results, magnitude, interleave, add_states) -> str

    Return a string which shows a trace of the effects of the found pulse
    sequence on the target state and the other optimised states.

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
        be appended to the automatically included states."""
    def format_complex(j):
        j = abs(j) if magnitude else j
        if abs(j) < 5e-8:
            return "0"
        elif abs(j.real) < 5e-18:
            return "{:.8g}i".format(j.imag)
        elif abs(j.imag) < 5e-18:
            return "{:.8g}".format(j.real)
        else:
            return "{:.8g} {} {:.8g}i".format(j.real,
                                               "+" if j.imag >= 0 else "-",
                                               abs(j.imag))
    def all_traces(states, sequence, parameters):
        ns = states[0].dims[0][1]
        def mapping(state):
            trace = sequence.trace(parameters, state)
            kets = [ el.full().reshape((2 * ns,)) for el in trace ]
            return np.array([ list(map(format_complex, ket)) for ket in kets ])
        return np.array(list(map(mapping, states)), dtype='<U32')
    def left_pad(strings):
        for pulse in range(strings.shape[0]):
            len_max = 0
            for state in range(strings.shape[1]):
                for el in range(strings.shape[2]):
                    len_max = max(len_max, len(strings[pulse, state, el]))
            for state in range(strings.shape[1]):
                for el in range(strings.shape[2]):
                    strings[pulse, state, el] =\
                        strings[pulse, state, el].rjust(len_max)
    states, sequence = run._prepare_parameters(results.run_parameters)
    ns = states[0].dims[0][1]
    states = np.append(states, [it.state.create(x, ns) for x in add_states])
    strs = all_traces(states, sequence, results.parameters) # [state, pulse, el]
    strs = np.transpose(strs, (1, 0, 2)) # [pulse, state, el]
    ket_names = [ "|{}{}>".format(x, n) for x in ["e", "g"] for n in range(ns) ]
    strs = np.insert(strs, 0, ket_names, 0) # strs now has |{}{}> prepended
    left_pad(strs)
    strs = np.transpose(strs, (1, 2, 0)) # [state, el, pulse]
    if interleave:
        order = [ n + x * ns for n in range(ns) for x in range(2) ]
        strs = strs[:,order,:]
    lines = np.array([[ " | ".join(strs[state, el])\
                        for el in range(strs.shape[1]) ]\
                      for state in range(strs.shape[0])])
    return "\n\n".join(map(lambda state: "\n".join(state), lines))
