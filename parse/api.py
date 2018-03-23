"""Top-level functions for the `projsearch.parse` module - this file should
typically not be accessed directly, since its name space is imported into the
top-level namespace `projsearch.parse`."""

from . import types, commands
from ..functional import exists
from ..run import RunParameters
import itertools

__all__ = ['machine_line', 'input_file_to_machine_lines',
           'input_file_to_parameters', 'user_input_to_machine_input',
           'key_value_statements']

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

def key_value_statements(file, s_sep=';', kv_sep='='):
    """key_value_statements(file: file object, ?s_sep, ?kv_sep) -> generator

    Returns a generator of dictionaries, for looping through a file
    statement-by-statement, removing comments and whitespace as necessary.

    Arguments:
    file: file object -- A file opened for reading in string mode.
    s_sep: string --
        The string which is considered to separate statements which occur on the
        same line.
    kv_sep: string -- The string which separates the key from its value.

    Returns:
    generator of dict with keys:
        'key': str -- the "key" side of the pair.
        'value': str -- the "value" side of the pair.
        'line': int > 0 -- the line number the statement was found on.
        'statement': str -- the whole statement that was parsed."""
    for line_num, line in enumerate(file):
        for stmt in map(lambda s: s.strip(), _cut_comment(line).split(s_sep)):
            if stmt == '':
                continue
            parts = list(map(lambda s: s.strip(), stmt.split(kv_sep)))
            if len(parts) is not 2 or exists(lambda s: s == '', parts):
                raise ValueError("Could not interpret statement '" + stmt
                                 + "' on line {} of '".format(line_num + 1)
                                 + file.name + "'.")
            else:
                yield {'key': parts[0], 'value': parts[1],
                       'line': line_num + 1, 'statement': stmt}


def input_file_to_machine_lines(file_name):
    """input_file_to_machine_lines(file_name: str) -> generator of str

    Acquire the lock on the human-readable input file with path `file_name`,
    then return an iterator which yields each machine-readable line specified in
    order.  Commands in the input file which produce ranges will be treated like
    for loops, with the first encountered sequence being the outer-most loop.

    The generator will close the file when it encounters an unreadable line, or
    when the generator is fully consumed."""
    cur_order = []
    with open(file_name) as file:
        for stmt in key_value_statements(file):
            if exists(lambda t: t[0] == stmt['key'], cur_order):
                raise ValueError(
                    "Encountered another specifier for '" + stmt['key'] + "'"
                    + " on line {}".format(stmt['line'])
                    + " before the previous input set was completed.")
            elif stmt['key'] not in _needed_params:
                raise ValueError(
                    "Encountered unknown parameter specifier '"
                    + stmt['key'] + "' in statement '" + stmt['statement'] + "'"
                    + " on line {}".format(stmt['line']))
            cur_order.append((stmt['key'], stmt['value']))
            if set(map(lambda t: t[0], cur_order)) == _needed_params:
                yield from commands.expand(cur_order)
                cur_order = []
    if cur_order != []:
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
