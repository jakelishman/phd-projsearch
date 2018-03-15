import numpy as np
import iontools as it
import qutip
import scipy.linalg

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

def target(states, sequence):
    """target(states, sequence) -> params -> float * np.array of float

    Returns a function which takes the parameter vector as an argument, and
    returns a tuple of the infidelity, and the derivatives of the infidelity
    with respect to each of the parameters.

    This is intended for use with
        scipy.optimize.minimize(target(states, sequence), params, jac=True)

    Arguments:
    states: np.array of qutip.Qobj --
        An array of a set of orthonormal basis vectors.  The first state in the
        array is the target state, which we will try to optimise to put entirely
        in the excited state.  All other states will be moved into the ground
        state.

        All states should be of the same number of motional levels considered,
        which should also match the dimensionality of the sequence.  There
        should be enough space to fit all calculations in without overflowing
        the arrays.

    sequence: iontools.Sequence --
        The pulse sequence to apply.  The parameters to the sequence will be
        varied, but the order of the pulses will be the same throughout.

    Returns:
    np.array of float -> float * np.array of float --
        A function which takes a vector of parameters (of length 2 * number of
        pulses in sequence, i.e. [time, phase, time, phase, ...]) and returns
        the value of the infidelity of the gate operation and its derivatives
        with respect to each of the parameters."""
    e_bra, g_bra = it.state.qubit_projectors(states[0])
    bras = np.array([g_bra] + [e_bra] * (len(states) - 1))
    def func(params):
        op = sequence.op(params)
        infid = (g_bra * op * states[0]).norm() ** 2
        for i in range(len(states) - 1):
            infid += (e_bra * op * states[i + 1]).norm() ** 2
        deriv = np.zeros_like(params)
        op_proj = bras * op * states
        for (i, d_op) in enumerate(sequence.d_op(params)):
            for (oper, d_oper) in zip(op_proj, bras * d_op * states):
                deriv[i] += 2 * np.real((oper.dag() * d_oper).data[0, 0])
        return infid, deriv
    return func
