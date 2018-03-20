#!/bin/bash

# SYNOPSIS
#   submit.sh [options]
#
# OPTIONS
#   -c | --conda conda_source
#       Location of the file 'conda.sh' which is sourced to load conda into the
#       path for execution.  If not specified, this script attempts to search
#       some locations for it.
#
#   -d | --debug
#       Debug run.  This will print out more information about the execution of
#       the script, and won't submit the job to qsub at the end.
#
#   -f | --force-output
#       Use the chosen output directory even if it contains files.  This could
#       result in data loss!
#
#   -i | --input input_file (default = stdin)
#       Read the targets file from "input_file" rather than from the default of
#       stdin.  If multiple '-i' flags are given, the files will be read as if
#       they had been concatenated in the order they're specified.
#
#   -o | --output outdir (default = .)
#       The directory to place the output files from the run in.  Assumed to be
#       "." if not supplied.
#
#   -w | --walltime walltime (default = 24:00:00)
#       The amount of walltime to request from the scheduler per task.

# Attempt to locate the conda.sh file necessary to source conda and activate
# environments.  Prints the location of the file to stdout if successful, or
# returns non-zero if it cannot find the file.
try_find_conda_sh() {
    local script_relative_path="anaconda3/etc/profile.d/conda.sh"
    for conda_root in "$HOME/.anaconda" "$HOME/.anaconda3" "$HOME/anaconda"\
                      "$HOME/anaconda3" "$HOME"; do
        if [[ -e "$conda_root/$script_relative_path" ]]; then
            echo "$conda_root/$script_relative_path"
            return 0
        fi
    done
    echo "ERROR: couldn't find a path to source conda from." >&2
    echo "       Consider specifying the '--conda' argument to this script." >&2
    return 1
}

# Attempt to make a directory and exit if it fails.
make_directory() {
    mkdir -p "$1" 2>/dev/null
    if [[ ! $? = 0 ]]; then
        echo "ERROR: couldn't make the directory '$1'" >&2
        exit 1
    fi
}

# Fill in any options which need to be filled to continue, and have sensible
# defaults.
fill_missing_parameters() {
    if [[ -z $opts_debug ]]; then opts_debug=false; fi
    # We don't set the input files because it will be stdin by default.
    if [[ -z $opts_output_dir ]]; then
        opts_output_dir="$(pwd -P)/output"
        make_directory "$opts_output_dir"
    fi
    if [[ -z $opts_conda_sh ]]; then
        opts_conda_sh=$(try_find_conda_sh)
        local code="$?"
        if [[ "$code" -ne "0" ]]; then
            exit "$code"
        fi
    fi
    if [[ -z $opts_walltime ]]; then opts_walltime=24:00:00; fi
}

# Exit the script with an error message if a variable is already set.
#
# Usage: fail_if_set string name
#   string: string to test if it has content.
#   name: name of the flag which this string is associated with.
fail_if_set() {
    if [[ ! -z "$1" ]]; then
        echo "ERROR: the '$2' flag has been set multiple times." >&2
        exit 1
    fi
}

# Exit the script with an error message if there is no argument.
#
# Usage: fail_if_no_arg string name
#   string: string to test if empty.
#   name: name of flag which this string is associated with.
fail_if_no_arg() {
    if [[ -z "$1" ]]; then
        echo "ERROR: you must supply an argument to the '$2' flag." >&2
        exit 1
    fi
}

# Exit the script if an input file couldn't be found.
#
# Usage: fail_if_file_does_not_exist file
#   file: file to test
fail_if_file_does_not_exist() {
    if [[ ! -e "$1" ]]; then
        echo "ERROR: can't find the file '$1'." >&2
        exit 1
    fi
}

# Print out the parameter list to standard output.  Takes no arguments.
print_parameters() {
    echo "\$opts_debug        : '$opts_debug'"
    echo "\$opts_conda_sh     : '$opts_conda_sh'"
    echo "\$opts_output_dir   : '$opts_output_dir'"
    echo "\$opts_walltime     : '$opts_walltime'"
    echo "\$opts_force_output : '$opts_force_output'"
    echo "\$python_path       : '$python_path'"
    echo -n "\$opts_input_files  :"
    if [[ -z "${opts_input_files[0]}" ]]; then
        echo " ''"
    else
        echo " '{"
        for file in "${opts_input_files[@]}"; do
            echo "    \"$file\","
        done
        echo "}'"
    fi
}

# Print a string pointing to the location of the python module given in $1.
python_modpath() {
    python -c "import imp; print(imp.find_module('$1')[1])" 2>/dev/null
}

# Copy all python modules in the array ${python_necessary_modules} into the
# directory $1, transforming symlinks to directories into the actual directories
# so that the code which is run by python will have absolutely fixed values.
stash_python_modules() {
    make_directory "$1"
    for module in "${python_necessary_modules[@]}"; do
        local modpath=`python_modpath "${module}"`
        if [[ -z "$modpath" ]]; then
            echo "ERROR: couldn't find module '${module}'" >&2
            exit 1
        fi
        if [[ -f "$modpath" ]]; then
            cp "$modpath" "$1"
        elif [[ -d "$modpath" ]]; then
            rsync -ak --exclude='*/.git' --exclude='*/__pycache__'\
                "${modpath%/}" "$1"
        fi
    done
}

# Fail if the directory $1 is non-empty.
check_output_dir_safe() {
    if [[ ! -z "$(ls -A "$2")" ]]; then
        echo "ERROR: output directory is not empty." >&2
        echo "       Consider passing option --force-output to override." >&2
        exit 1
    fi
}

# Command-line option initialisation.
opts_debug=
opts_input_files=
opts_conda_sh=
opts_output_dir=
opts_walltime=
opts_force_output=false

# Separator character for file names.
file_sep=";"

# Output files that will be written.
output_inputs_file="inputs_file"
output_machine_inputs_file="machine_inputs_file"
output_failure_file="failure"
output_success_file="success"
output_parameters_file="parameters"
output_submission_file="submission"

# Parse the command line arguments.
while (($#)); do
    case "$1" in
        "-c" | "--conda")
            fail_if_set "$opts_conda_sh" "$1"
            fail_if_no_arg "$2" "$1"
            fail_if_file_does_not_exist "$2"
            opts_conda_sh="$2"
            shift ;;

        "-d" | "--debug")
            opts_debug=true ;;

        "-f" | "--force-output")
            opts_force_output=true ;;

        "-i" | "--input")
            fail_if_no_arg "$2" "$1"
            fail_if_file_does_not_exist "$2"
            if [[ -z $opts_input_files ]]; then
                opts_input_files="$(realpath "$2")"
            else
                opts_input_files+="${file_sep}$(realpath "$2")"
            fi
            shift;;

        "-o" | "--output")
            fail_if_set "$opts_output_dir" "$1"
            fail_if_no_arg "$2" "$1"
            # Create the output directory if necessary.
            make_directory "$2"
            opts_output_dir="$(realpath "$2")"
            shift ;;

        "-w" | "--walltime")
            fail_if_set "$opts_walltime" "$1"
            fail_if_no_arg "$2" "$1"
            opts_walltime="$2" ;;

        *)
            echo "ERROR: unknown argument '$1'" >&2
            exit 1 ;;
    esac
    shift
done

# Split the ':' separated string of filenames into an array of files.
IFS="${file_sep}" read -r -a opts_input_files <<< "$opts_input_files"

if [[ $opts_debug = true ]]; then
    echo "After reading command line options, I have" >&2
    print_parameters >&2
fi

fill_missing_parameters

if [[ $opts_debug = true ]]; then
    echo >&2
    echo "After filling in any necessary missing parameters, I have" >&2
    print_parameters >&2
fi

# Unless told otherwise, we should check that the output directory is safe for
# us to put files into.
if [[ ! "$opts_force_output" = true ]]; then
    check_output_dir_safe "${opts_output_dir}"
fi

# Change into the output directory for making the files.
cd "$opts_output_dir"

echo "Time submitted: $(date +"%F %T")" > "$output_parameters_file"
print_parameters >> "$output_parameters_file"

# Save the input parameters into the relevant file.
if [[ -z "$opts_input_files" ]]; then
    echo '# === [stdin] ===' > "$output_inputs_file"
    cat >> "$output_inputs_file"
    echo >> "$output_inputs_file"
else
    rm -f "$output_inputs_file"
    for input in "${opts_input_files[@]}"; do
        echo "# === ${input} ===" >> "$output_inputs_file"
        cat "${input}" >> "$output_inputs_file"
        echo >> "$output_inputs_file"
    done
fi

# Stash python modules in the right place.
python_code_dir="${opts_output_dir}/python"
python_entry_point="${python_code_dir}/_projsearch_entry.py"
python_path="${python_code_dir}:${PYTHONPATH}"
make_directory "${python_code_dir}"
declare -a python_necessary_modules
python_necessary_modules=("iontools" "projsearch")
stash_python_modules "${python_code_dir}"

# Load up a conda environment so we can run the input building commands.
source "${opts_conda_sh}"
qutip_environment="qutip"
conda activate "${qutip_environment}"

# Build the input commands
python << PythonScriptEnd
from projsearch import parse
parse.user_input_to_machine_input("$output_inputs_file",
                                  "$output_machine_inputs_file")
PythonScriptEnd
if [[ ! $? -eq 0 ]]; then
    echo "ERROR: couldn't parse input file." >&2
    exit 1
fi
njobs=$(wc -l ${output_machine_inputs_file} | cut -d ' ' -f1)

cat > "${python_entry_point}" << PythonScriptEnd
if __name__ == '__main__':
    import projsearch, projsearch.parse, sys

    if len(sys.argv) is not 3 and len(sys.argv) is not 2:
        print("Error: program not called correctly.", file=sys.stderr)
        exit(1)

    lines = sys.stdin.readlines()
    if len(lines) is not 1:
        print("Error: improper input on stdin.", file=sys.stderr)
        exit(2)
    run_params = projsearch.parse.machine_line(lines[0])
    projsearch.single_sequence(run_params, *sys.argv[1:])
PythonScriptEnd

if [[ $opts_debug = true ]]; then
    echo >&2
    echo "Final parameters before writing the script are:" >&2
    print_parameters >&2
fi

# Write out the script into the right place.
cat > ${output_submission_file} << ScriptEnd
#!/bin/bash
#PBS -l walltime=${opts_walltime}
#PBS -l select=1:ncpus=1:mem=1gb
#PBS -J 1-${njobs}

# Set up Python correctly
export PYTHONPATH="${python_path}"
source "${opts_conda_sh}"
conda activate "${qutip_environment}"

success_file="${output_success_file}_\${PBS_ARRAY_INDEX}"
#failure_file="${output_failure_file}_\${PBS_ARRAY_INDEX}"

head -n "\${PBS_ARRAY_INDEX}" "${output_machine_inputs_file}" \\
    | tail -n-1 \\
    | python -O "${python_entry_point}" "\${success_file}" #"\${failure_file}"

cp "\${success_file}" "${opts_output_dir}"/
ScriptEnd

if [[ "$opts_debug" = false ]]; then
    qsub "${output_submission_file}"
fi
