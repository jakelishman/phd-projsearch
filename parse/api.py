"""Top-level functions for the `projsearch.parse` module - this file should
typically not be accessed directly, since its name space is imported into the
top-level namespace `projsearch.parse`."""

from . import types, commands
from ..functional import exists
from ..run import RunParameters
import itertools

__all__ = ['machine_line', 'input_file_to_machine_lines',
           'input_file_to_parameters', 'user_input_to_machine_input']

_needed_params = set(["state", "sequence", "laser", "time"])

def machine_line(str):
    """machine_line(str: string) -> RunParameters

    Parse a single string from the machine-readable file into a set of
    RunParameters which can be used to run a single optimisation.

    The machine-readable string should look like
        state={'g1':1,'g0':1j};sequence=[0,1];laser=(0,0.1,1000);time=3600
    or something similar.  Importantly, it should be entirely on a single line
    with 'key=val' pairs separated by a ';'.  All other whitespace is ignored,
    so can be included for human readability if desired.

    Raises:
    ValueError -- if there were issues in parsing."""
    def keyval(part):
        sides = [ x.strip() for x in part.split("=") ]
        if len(sides) is not 2 or exists(lambda x: x is "", sides):
            raise ValueError("Could not parse '{}' for a key-val pair."
                             .format(part.strip()))
        return sides
    dict_ = dict(map(keyval, filter(lambda x: x.strip() != "", str.split(";"))))
    got = set(dict_)
    if _needed_params - got != set():
        raise ValueError("Did not get a value for {} in entry '{}'."
                         .format(_needed_params - got, str.strip()))
    elif got - _needed_params != set():
        raise ValueError("Found extra keys {} in entry '{}'."
                         .format(got - _needed_params, str.strip()))
    return RunParameters(types.state(dict_["state"]),
                         types.sequence(dict_["sequence"]),
                         types.laser(dict_["laser"]),
                         types.time(dict_["time"]))

def _cut_comment(str_):
    """_cut_comment(str_: str) -> str

    Return a slice of the input string which has any present comment removed.  A
    comment begins with the character '#', and runs til the end of the line.
    This functions returns everything before the comment character."""
    comment_start = str_.find('#')
    if comment_start is -1:
        return str_
    else:
        return str_[:comment_start]

def input_file_to_machine_lines(file_name):
    """input_file_to_machine_lines(file_name: str) -> generator of str

    Acquire the lock on the human-readable input file with path `file_name`,
    then return an iterator which yields each machine-readable line specified in
    order.  Commands in the input file which produce ranges will be treated like
    for loops, with the first encountered sequence being the outer-most loop.

    The generator will close the file when it encounters an unreadable line, or
    when the generator is fully consumed."""
    cur_dict = {}
    cur_order = []
    with open(file_name) as file:
        for line_num, line in enumerate(file):
            statements = map(lambda s: s.strip(), _cut_comment(line).split(";"))
            for statement in statements:
                if statement == '':
                    continue
                parts = list(map(lambda s: s.strip(), statement.split("=")))
                if len(parts) is not 2\
                   or parts[0] not in _needed_params\
                   or parts[1] is '':
                    raise ValueError(
                        "Could not interpret statement '" + statement + "'"
                        + " on line {}.".format(line_num + 1))
                elif parts[0] in cur_dict:
                    raise ValueError(
                        "Encountered another specifier for '" + parts[0] + "'"
                        + " on line {}".format(line_num + 1)
                        + " before the previous input set was completed.")
                elif parts[0] not in _needed_params:
                    raise ValueError(
                        "Encountered unknown parameter specifier '"
                        + parts[0] + "' in statement '" + statement + "'"
                        + " on line {}".format(line_num + 1))
                else:
                    cur_dict[parts[0]] = parts[1]
                    cur_order.append(parts[0])
                if set(cur_dict) == _needed_params:
                    yield from commands.expand(cur_dict, cur_order)
                    cur_dict = {}
                    cur_order = []
        if cur_dict != {}:
            raise ValueError("End-of-file encountered "
                             + "before the last specifier was complete.")

def input_file_to_parameters(file_name):
    """input_file_to_parameters(file_name: str) -> generator of RunParameters

    Acquire the lock on the human-readable input file with path `file_name`,
    then return an iterator which yields each set of RunParameters in file
    order.  Commands in the input file which produce ranges will be treated like
    for loops, with the first encountered sequence being the outer-most loop.

    The generator will close the file when it encounters an unreadable line, or
    when the generator is fully consumed."""
    return map(machine_line, input_file_to_machine_lines(file_name))

def user_input_to_machine_input(user_file_name, machine_file_name):
    """user_input_to_machine_input(user_file_name: str, machine_file_name: str)
    -> None

    Converts a single user input file into machine-readable lines which are then
    appended to the (possibly non-existing) file called `machine_file_name`."""
    with open(machine_file_name, "a") as out:
        for line in input_file_to_machine_lines(user_file_name):
            out.write(line + "\n")
