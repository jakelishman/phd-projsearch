"""Contains functions to convert the values of parameters back into strings for
writing to machine-readable files."""

def state(dict_):
    """state(dict_: dictionary of (state: str) * (value: complex)) -> str

    Convert a dictionary specifying a state into a string representation."""
    return "{" + ",".join(['"'+k+'":'+ str(v) for k, v in dict_.items()]) + "}"

def sequence(seq):
    """sequence(seq: iterable of int) -> str

    Convert an interable of integers representing the orders of the sidebands
    making up a sequence into a string representation."""
    return "[" + ",".join(map(str, seq)) + "]"

def laser(laser_):
    """laser(laser_: iontools.Laser) -> str

    Convert a laser class into a string representation of the tuple of arguments
    which can be used to instantiate it, i.e. a string representation of
    (detuning, lamb_dicke, base_rabi)."""
    return "(" + str(laser_.detuning) + ","\
           + str(laser_.lamb_dicke) + ","\
           + str(laser_.base_rabi) + ")"

def time(time):
    """time(time: float) -> str

    Return a string representing the time."""
    return str(time)
