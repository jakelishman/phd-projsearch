from functools import partial

class filter_results:
    """Treat the return value of this as a function which can be used as a
    callback taking an scipy.optimise.OptimiseResult as an argument.

    The filter stores the state of the best result so far, then passes "better"
    results onto the `success_callback1, and (optionally) worse results onto the
    `failure_callback`.  A result is "better" if the `compare` function returns
    True."""
    def __init__(self, success_callback, failure_callback=None,
                 compare=(lambda x, y: x < y),
                 initial_value=None):
        """Arguments:
        success_callback: scipy.optimize.OptimizeResult -> None --
            The callback to call with the result of an optimisation that is
            "better" than any previous result passed through this filter.

        failure_callback (optional): scipy.optimize.OptimizeResult -> None --
            The callback to call with the result of an optimisation that is
            "worse" than the previous best result passed through this filter.

        compare (optional): 'A * 'A -> bool
        with
            'A: type of the return value of the function being optimised --
            The function to use to compare two values.  The first argument is
            the newest result, and the second argument is the previous best
            result.

            If `compare` returns True, then the new value will be considered
            "better" than the previous best.

            The default is the "less than" function, i.e. it's set up to
            minimise the results.

        initial_value (optional): 'A with 'A: return value of optimise target --
            The value to use for the first "best" value.  If this is not passed,
            then the filter will take the first successful result passed through
            it to be the best.

        Returns:
        scipy.optimize.OptimizeResult -> None --
            A single callback which sorts subsequent results into "better" or
            "worse" than the previous results.  Better results are passed to the
            success callback, and worse ones are passed to the failure callback.
        """
        self.success_callback = success_callback
        self.failure_callback = failure_callback
        self.compare = compare
        self.best_value = initial_value

    def __call__(self, optimise_result):
        if not optimise_result.success:
            return
        elif self.best_value is None \
             or self.compare(optimise_result.fun, self.best_value):
            self.best_value = optimise_result.fun
            return self.success_callback(optimise_result)
        elif self.failure_callback is not None:
            return self.failure_callback(optimise_result)

def test_filter():
    return filter_results(lambda res: print("Success: {}".format(res.fun)),
                          lambda res: print("Failure: {}".format(res.fun)))

def print_key_val(key, val, indent=0, **kwargs):
    return print(indent * "    " + key + " = " + val, **kwargs)

def float_array_string(arr):
    return "[" + ", ".join(map(str, arr)) + "]"

def print_result(res, indent=0, **kwargs):
    print_kv = partial(print_key_val, indent=indent, **kwargs)
    print_kv("infidelity", str(res.fun))
    print_kv("parameters", float_array_string(res.x))
    print_kv("success", str(res.success))
    print("", **kwargs)

def print_info(run_params, indent=0, **kwargs):
    print_kv = partial(print_key_val, indent=indent, **kwargs)
    print_kv("state", str(dict(run_params.state)))
    print_kv("sequence", str(list(run_params.sequence)))
    laser = run_params.laser
    laser_str = "({}, {}, {})".format(laser.detuning, laser.lamb_dicke,
                                      laser.base_rabi)
    print_kv("laser", laser_str)
    print_kv("time", str(run_params.time))

def file_filter(success_file, failure_file=None):
    def callback(file):
        return lambda res: print_result(res, indent=1, file=file, flush=True)
    if failure_file is None:
        return filter_results(callback(success_file))
    return filter_results(callback(success_file), callback(failure_file))
