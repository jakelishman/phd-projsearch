"""Main entry point for the projsearch module, which include the function to
minimise a result over time, and handles the setup for a set of run
parameters."""
from . import output

import iontools as it
import os
import qutip
import numpy as np
import scipy.optimize
import scipy.linalg
import time

__all__ = ['single_sequence', 'minimise_over_time', 'target', 'RunParameters',
           'prepare_parameters']

class RunParameters:
    """A set of parameters that can be passed to the function runners to run a
    single instance of the optimiser.

    All the arguments to `__init__` are available as properties with the same
    types and the same names."""
    def __init__(self, state, sequence, laser, time):
        """Arguments:
        state: dict of string * complex --
            A dictionary linking elements of a state vector specified as strings
            (e.g. `"g1"` or `"e29"`) and their complex coefficients.  This
            dictionary will be turned into a state which is normalised, but
            keeps the relative phases and magnitudes of the coefficients.

        sequence: iterable of int --
            The pulse sequence to apply in numerical form, where 0 is the
            carrier, -1 is the first red, 2 is the second blue and so on.  The
            pulse sequence will be applied so that the first element of the
            iterator is the first pulse applied to the state.

        laser: (detuning: float) * (lamb_dicke: float) * (base_rabi: float) --
            The same arguments which will be passed to create an instance of the
            class `iontools.Laser`.

        time: float in s --
            The amount of walltime to optimise the parameters over.  The actual
            time used will exceed this measure by up to the amount of time
            needed for one optimisation run."""
        self.state = state
        self.sequence = sequence
        self.laser = laser
        self.time = time

def _named_field(array, field):
    """Extract a new array from `array` which consists only of the elements in
    the field `field`."""
    return array.getfield(*array.dtype.fields[field])

def linear_independent_set(state):
    """linear_independent_set(state: qutip.Qobj) -> np.array of qutip.Qobj

    Given a 2-level system coupled to a Fock space, return a set of additional
    state vectors, which when combined with the original input, create a
    linearly independent basis spanning the subspace formed by only considering
    (qubit tensor Fock) states that are populated in the input vector.

    For example,
        linear_independent_set((|g0> + |e2> + |e3>)/sqrt(3))
    will return something like the vectors |g0> and |e2>, which together with
    the original input span the complex space defined as
        c_0 |g0> + c_1 |e2> + c_2 |e3>
    with {c_i} all complex."""
    populated = it.state.populated_elements(state)
    ns = it.state.ns(state)
    return np.array([it.state.create({el: 1}, ns=ns)
                     for el in _named_field(populated[1:], "element")])

def orthonormal_basis(state):
    """orthonormal_basis(state: qutip.Qobj) -> np.array of qutip.Qobj

    Returns the vectors needed to make an orthonormal basis over the subspace
    defined by the populated elements in the input state.  The first vector in
    the returned array will always be the normalised version of the input state.
    """
    ns = it.state.ns(state)
    populated = it.state.populated_elements(state)
    els = _named_field(populated, "element")
    values = _named_field(populated, "value")
    others = [it.state.element(ket, els)
              for ket in linear_independent_set(state)]
    # NOTE: uses undocumented behaviour of scipy.linalg.qr to achieve this - we
    # assume that we reliably have the input state at the first output in the QR
    # decomposition.  If this changes, we can do a manual QR decomposition to
    # guarantee it.
    vecs = -scipy.linalg.qr(np.array([values] + others).T)[0].T
    out = np.array([it.state.create(zip(els, vec), ns=ns) for vec in vecs])
    assert abs((state.unit().dag() * out[0]).norm() - 1) < 1e-8
    return out

def prepare_parameters(run_params, with_derivative=True):
    """prepare_parameters(run_params: RunParameters)
    -> np.array of qutip.Qobj * iontool.Sequence

    Convert a set of `RunParameters` into an orthonormal basis set of states and
    an `iontools.Sequence` object of sufficient size to run the sequence.

    The first state in the state array will always be the target state from the
    `RunParameters`."""
    pairs = run_params.state.items() if isinstance(run_params.state, dict)\
            else list(run_params.state)
    ns = 1 + int(max(map(lambda t: t[0], pairs), key=lambda k: int(k[1:]))[1:])
    ns += sum(map(np.abs, run_params.sequence))
    start_state = it.state.create(run_params.state, ns=ns)
    sidebands = map(lambda x: it.Sideband(ns, x, run_params.laser),
                    run_params.sequence)
    return orthonormal_basis(start_state),\
           it.Sequence(sidebands, derivatives=with_derivative)

def target(run_params, with_derivative=True):
    """target(run_params: RunParameters, with_derivative: bool)
    -> (np.array of float -> float * np.array of float)

    Returns a function which takes the parameter vector as an argument, and
    returns a tuple of the infidelity, and the derivatives of the infidelity
    with respect to each of the parameters.

    This is intended for use with
        scipy.optimize.minimize(target(run_params), params, jac=True)

    Returns:
    np.array of float -> float * np.array of float --
        A function which takes a vector of parameters (of length 2 * number of
        pulses in sequence, i.e. [time, phase, time, phase, ...]) and returns
        the value of the infidelity of the gate operation and its derivatives
        with respect to each of the parameters.

    np.array of float -> float --
        If `with_derivative` is false, then only calculate the infidelity."""
    states, sequence = prepare_parameters(run_params, with_derivative)
    e_bra, g_bra = it.state.qubit_projectors(states[0])
    bras = np.array([g_bra] + [e_bra] * (len(states) - 1))
    scale = 1.0 / len(states)
    def func(params):
        op = sequence.op(params)
        infid = (g_bra * op * states[0]).norm() ** 2
        for i in range(len(states) - 1):
            infid += (e_bra * op * states[i + 1]).norm() ** 2
        if not with_derivative:
            return infid * scale
        deriv = np.zeros_like(params)
        op_proj = bras * op * states
        for (i, d_op) in enumerate(sequence.d_op(params)):
            for (oper, d_oper) in zip(op_proj, bras * d_op * states):
                deriv[i] += 2 * np.real((oper.dag() * d_oper).data[0, 0])
        return infid * scale, deriv * scale
    return func

def minimise_over_time(func, gen_init_params, callback, time_limit):
    """minimise_over_time(func, gen_init_params, callback, time_limit) -> None

    Repeatedly minimise a function until an amount of time `time_limit` has
    passed.  For each run, the initial parameters to use are generated by
    `gen_init_params` and the result is passed to the `callback` function.

    Arguments:
    func: np.array of 'T -> float * np.array of float --
        The function to be minimised over time.  This should return a tuple of
        the value to be minimised, and the derivatives of that argument with
        respect to the input parameters.

    gen_init_params: None -> np.array of 'T --
        A function which when called will return a set of input parameters to
        use as the initial guess for `func`.  This should be different each time
        it is called, or the minimisation will never improve.

    callback: OptimizeResult -> None --
        This function is called with each result, so should handle what is to be
        done with them.  Each callback is run synchronously, so the next
        minimisation routine will not start until it has completed.

    time_limit: numeric in seconds --
        The amount of time to run the minimiser for.  This time limit can be
        exceeded by up to the length of time taken for one minimisation run."""
    start = time.clock()
    while time.clock() - start < time_limit:
        callback(scipy.optimize.minimize(func, gen_init_params(),
                                         method='bfgs', jac=True))
    return

def _maximums_generator(sequence, rabi, nperiods):
    """For a given sequence, generate the values that should be used as the
    maximum of the random distribution that its parameters will be drawn
    from.

    Arguments:
    sequence: iterable of int -- the orders of the sidebands to be applied.
    rabi: dict of (int >= 0) * float --
        The values of the Rabi frequencies coupling motional levels 0 and n.
        As long as all the Rabi frequencies that will be needed for `sequence`
        are included (that couple to the 0 level), that is sufficient.
    nperiods: float -- How many periods to draw time from."""
    for sideband in sequence:
        yield 2 * np.pi * nperiods / rabi[abs(sideband)]
        yield 2 * np.pi

class _make_random:
    """After creation, treat this as a function which gives a reasonable set of
    random parameters to use for each optimisation run for the given
    RunParameters.  Example usage:
        randoms = _make_random(params) # so randoms() -> np.array of float
        while True:
            minimise(target_function, inits=randoms)

    Instantiating this class makes a function which can be called to give a new
    set of random parameters to start with."""
    def __init__(self, run_params, nperiods=3):
        """Arguments:
        run_params: RunParameters -- the parameters for the optimisation run.
        nperiods: int > 0 --
            The initial values for the length of time to run a single pulse for
            will be randomly distributed over its time period * `nperiods`.  For
            example, if a sideband has a Rabi frequency of 1, we will draw
            its starting times from the range (0, 2 * pi * nperiods).

            The period is defined as the period of the Rabi transition of the
            `(0, abs(n))` coupling, where `n` is the order of the sideband."""
        orders = set(map(abs, run_params.sequence))
        rabi = dict([(x, run_params.laser.rabi_mod(0, x)) for x in orders])
        self.max = list(_maximums_generator(run_params.sequence,rabi, nperiods))

    def __call__(self):
        return np.array([np.random.uniform(0.0, max) for max in self.max])

def _open_if_needed(file_name, mode):
    """Open a file as a file object if it is not None, or return a dummy output
    stream if it is."""
    if file_name is None: return open(os.devnull, "w")
    else: return open(file_name, mode)

def single_sequence(run_params, success_file, failure_file=None):
    """single_sequence(run_params, success_file, ?failure_file) -> None

    From a given single set of RunParameters, optimise them over time to get the
    find the best possible parameters for the target.  This writes out a series
    of improving sets of parameters to the file at path `success_file`, and
    (optionally) all the other parameter sets it tries to `failure_file`."""
    with _open_if_needed(success_file, "w") as succ,\
         _open_if_needed(failure_file, "w") as fail:
        output.print_info(run_params, file=succ)
        output.print_info(run_params, file=fail)
        minimise_over_time(target(run_params), _make_random(run_params),
                           output.file_filter(succ, fail), run_params.time)
