import numpy as np
import iontools as it
import qutip
import scipy.linalg

def _named_field(array, field):
    """Extract a new array from `array` which consists only of the elements in
    the field `field`."""
    return array.getfield(*array.dtype.fields[field])

def qubit_projectors(target):
    """qubit_projectors(target: qutip.Qobj | int) -> qutip.Qobj * qutip.Qobj

    Given either an example state (2-level system tensor Fock basis) or a number
    of motional states to be considered in the Fock basis, return a pair of the
    projectors onto the "e" and "g" subspaces respectively."""
    ns = target.dims[0][1] if isinstance(target, qutip.Qobj) else target
    return (qutip.tensor(qutip.basis(2, 0), qutip.qeye(ns)).dag(),
            qutip.tensor(qutip.basis(2, 1), qutip.qeye(ns)).dag())

def populated_elements(state):
    """populated_elements(state: qutip.Qobj) -> np.array of string * complex

    Given a state vector of a 2-level system tensor a Fock state, return a list
    of (name * value) pairs for each of the populated states.  `name` is a
    string of the qubit followed by the Fock level (e.g. "g0" or "e10"), and
    `value` is the complex value that was in the state."""
    digits = len(str(state.dims[0][1] - 1))
    return np.array([
        (qubit + str(i), val) \
        for qubit, proj in zip(["e", "g"], qubit_projectors(state)) \
        for i, val in enumerate((proj * state).full().flat) \
        if abs(val) > 1e-11
    ], dtype=np.dtype([("element", "U{}".format(digits+1)), ("value", "c16")]))

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
    populated = populated_elements(state)
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
    populated = populated_elements(state)
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
    e_bra, g_bra = qubit_projectors(states[0])
    bras = np.array([g_bra] + [e_bra] * (len(states) - 1))
    def func(params):
        op = sequence.op(params)
        infid = (g_bra * op * states[0]).norm() ** 2
        for i in range(len(states) - 1):
            infid += (e_bra * op * states[i + 1]).norm() ** 2
        deriv = np.zeros_like(params)
        op_proj = bras * sequence.op(params) * states
        for (i, d_op) in enumerate(sequence.d_op(params)):
            for (oper, d_oper) in zip(op_proj, bras * d_op * states):
                deriv[i] += 2 * np.real((oper.dag() * d_oper).data[0, 0])
        return infid, deriv
    return func
