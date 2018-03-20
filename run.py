from . import target, output

import iontools as it
import numpy as np
import scipy.optimize
import time

__all__ = ['single_sequence', 'minimise_over_time']

def minimise_over_time(func, gen_init_params, callback, time_limit):
    start = time.clock()
    while time.clock() - start < time_limit:
        callback(scipy.optimize.minimize(func, gen_init_params(), jac=True))
    return

def prepare_sequence(run_params):
    pairs = run_params.state.items() if isinstance(run_params.state, dict)\
            else list(run_params.state)
    ns = 1 + int(max(map(lambda t: t[0], pairs), key=lambda k: int(k[1:]))[1:])
    ns += max(map(np.abs, run_params.sequence))
    start_state = it.state.create(run_params.state, ns=ns)
    sidebands = map(lambda x: it.Sideband(ns, x, run_params.laser),
                    run_params.sequence)
    return target.orthonormal_basis(start_state), it.Sequence(*sidebands)

def _maximums_generator(sequence, rabi, nperiods):
    for sideband in sequence:
        yield 2 * np.pi * nperiods / rabi[abs(sideband)]
        yield 2 * np.pi

class _make_random:
    def __init__(self, run_params, nperiods=3):
        orders = set(map(abs, run_params.sequence))
        rabi = dict([(x, run_params.laser.rabi_mod(0, x)) for x in orders])
        self.max = list(_maximums_generator(run_params.sequence,rabi, nperiods))

    def __call__(self):
        return np.array([np.random.uniform(0.0, max) for max in self.max])

def single_sequence(run_params, success_file, failure_file=None):
    def runner(succ, fail):
        output.print_info(run_params, file=succ)
        if fail is not None:
            output.print_info(run_params, file=fail)
        minimise_over_time(
            target.target(*prepare_sequence(run_params)),
            _make_random(run_params),
            output.file_filter(succ, fail), run_params.time)
    if failure_file is not None:
        with open(success_file, "w") as succ,\
             open(failure_file, "w") as fail:
            runner(succ, fail)
    else:
        with open(success_file, "w") as succ:
            runner(succ, None)
