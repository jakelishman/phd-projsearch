"""Contains functions to convert strings into the parameters that they
represent."""
import ast
import iontools as it

def state(str):
    """state(str: string) -> dict

    Attempt to parse the given string as a dictionary which defines a target
    state (i.e. something which can be passed to `iontools.state.create()`.

    Raises:
    ValueError -- if unable to parse."""
    try: return dict(ast.literal_eval(str))
    except:
        raise ValueError("Could not parse the state '{}' as a dictionary."
                         .format(str))

def sequence(str):
    """sequence(str: string) -> list of int

    Attempt to parse the string into a sequence of integers, i.e. a sequence
    speficier which lists the sidebands to be used in order.

    Raises:
    ValueError -- if unable to parse."""
    try: return [int(x) for x in ast.literal_eval(str)]
    except:
        raise ValueError("Could not parse the sequence '{}' as a list of ints."
                         .format(str))

def laser(str):
    """laser(str: string) -> iontools.Laser

    Attempts to parse the string into a tuple of (detuning, lamb_dicke, rabi),
    i.e. the arguments to `iontools.Laser()`.  Returns the defined laser.

    Raises:
    ValueError -- if unable to parse."""
    try: return it.Laser(*[float(x) for x in ast.literal_eval(str)])
    except:
        raise ValueError("Could not parse the laser '{}' as ".format(str)
                         + "(detuning, lamb_dicke, base_rabi).")

def time(str):
    """time(str: string) -> float in seconds

    Attempts to parse the given string into a float, interpreted as a time in
    seconds.

    Raises:
    ValueError -- if unable to parse."""
    return float(str)
