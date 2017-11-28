#!/usr/bin/env python3

# Arguments:
# -h: help, -v: verbose mode -l testing level, -m mpi-tasks, -d sw4-exe-dir

import argparse
import os
import platform
import subprocess
import sys


#----(Currently not used)--------------------------------------------
def run_checks(checks):
    fail = False
    for elem in checks:
        pass_check = (checks[elem][0] > checks[elem][1])
        print("%(check)s    tolerance: %(tol)f   calculated: %(val)f    pass: %(pass)s" %
                {"check": elem, "tol": checks[elem][0], "val": checks[elem][1], "pass": pass_check})
        if not pass_check: fail = True
    return fail

#------------------------------------------------
def compare_one_line(base_file_name, test_file_name, errTol, absErrLimit, lineNum, verbose):

    success = True

    base_file = open(base_file_name)
    test_file = open(test_file_name)
    base_data = base_file.readlines() #reads all lines in the file
    test_data = test_file.readlines()

    # tmp
    #print('base_data file:', base_data)
    #print('test_data file:', test_data)

    base_file.close()
    test_file.close()
    if len(base_data) != len(test_data):
        print("WARNING: " + base_file_name + " and " + test_file_name + " are different lengths.")

    # for twilight tests, compare the 3 numbers on the last line of each file
    base_line = base_data[lineNum]
    test_line = test_data[lineNum]
    #print('base_line=', base_line)
    #print('test_line=', test_line)

    base_data = base_line.split() #base_data is a list of strings
    test_data = test_line.split()
    #print('base_data=', base_data)
    #print('test_data=', test_data)

    base_num = [float(x) for x in base_data] #base_num is a list of floats
    test_num = [float(x) for x in test_data]
    #print('base_num=', base_num);
    #print('test_num=', test_num);

    try:
        for jj in range(len(base_data)):
            t0 = test_num[jj]
            b0 = base_num[jj]
            re0 = 0
            if abs(b0) > absErrLimit: 
                re0 = abs(b0-t0)/abs(b0)
            else:
                re0 = abs(b0-t0)

            if verbose or re0 > errTol:
                print('INFO: compare_one_line: col=', jj, 'test=', t0, 'base=', b0, 'err=', re0);

            if re0 > errTol:
                print('ERROR: compare_one_line: err=', re0, '> tolerance=', errTol)
                success = False
            # end if
        # end for
    except:
        success = False

    base_file.close()
    test_file.close()
    
    return success

#------------------------------------------------
def guess_mpi_cmd(mpi_tasks, verbose):
    """Create an MPI command string based on machine-dependent default values.
    The local machine information is retrieved with platform.uname(). If
    mpi_tasks is less than or equal to zero, it will be set to a machine-
    dependent default value.
    """

    machine_defaults = {
        "node": {
            "quartz": {
                "tasknum": 36,
                "command": "srun -ppdebug -n {tasknum}",
            },
            "cab": {
                "tasknum": 16,
                "command": "srun -ppdebug -n {tasknum}",
            },
            "nid": {
                "tasknum": 64,
                "command": "srun -c 4 --cpu_bind=cores -n {tasknum}",
            },
            "fourier": {
                "tasknum": 4,
                "command": "mpirun -np {tasknum}",
            },
        },
        "system": {
            "linux": {
                "tasknum": 1,
                "command": "mpirun -np {tasknum}",
            },
        },
        "default": {
            "tasknum": 1,
            "command": "mpirun -np {tasknum}",
        },
    }

    uname = platform.uname()

    node_settings = {
        node_name : settings
        for node_name, settings
        in machine_defaults["node"].items()
        if node_name.casefold() in uname.node.casefold()
    }

    system_settings = {
        sys_name : settings
        for sys_name, settings
        in machine_defaults["system"].items()
        if sys_name.casefold() in uname.system.casefold()
    }

    if node_settings:
        if len(node_settings) > 1 and verbose:
            print("Warning: Detected multiple node types:")
            for node_name in node_settings:
                print("  {}".format(node_name))

        _, settings = node_settings.popitem()

    elif system_settings:
        if len(system_settings) > 1 and verbose:
            print("Warning: Detected multiple system types:")
            for sys_name in system_settings:
                print("  {}".format(sys_name))

        _, settings = system_settings.popitem()

    else:
        settings = machine_defaults["default"]

    mpirun_cmd = settings["command"].format(
        tasknum=(mpi_tasks if mpi_tasks > 0 else settings["tasknum"]),
    )

    if verbose:
        print("platform.uname():")
        for k, v in uname._asdict().items():
            print("  {}: {}".format(k, v))

        print('mpirun_cmd = {}'.format(mpirun_cmd))

    return mpirun_cmd

#------------------------------------------------
def main_test(sw4_exe_dir="optimize", testing_level=0, mpi_tasks=0, verbose=False):
    sep = '/'
    pytest_dir = os.getcwd()
    pytest_dir_list = pytest_dir.split(sep)
    sw4_base_list = pytest_dir_list[:-1] # discard the last sub-directory (pytest)

    sw4_base_dir = sep.join(sw4_base_list)
    optimize_dir =  sw4_base_dir + sep + sw4_exe_dir
    reference_dir = pytest_dir + '/reference'

    # make sure the directories are there
    if not os.path.isdir(sw4_base_dir):
        print("ERROR: directory", sw4_base_dir, "does not exists")
        return False
    if not os.path.isdir(optimize_dir):
        print("ERROR: directory", optimize_dir, "does not exists (HINT: use -d 'sw4_exe_dir')")
        return False
    if not os.path.isdir(reference_dir):
        print("ERROR: directory", reference_dir, "does not exists")
        return False
    
    if verbose: print('pytest_dir =', pytest_dir)
    if verbose: print('sw4_base_dir =', sw4_base_dir)
    if verbose: print('optimize_dir =', optimize_dir)          
    if verbose: print('reference_dir =', reference_dir)          
    
    sw4_exe = optimize_dir + '/sw4'
    #print('sw4-exe = ', sw4_exe)

    # make sure sw4 is present in the optimize dir
    if not os.path.isfile(sw4_exe):
        print("ERROR: the file", sw4_exe, "does not exists (DID YOU FORGET TO BUILD SW4?)")
        return False

    # guess the mpi run command from the uname info
    mpirun_cmd=guess_mpi_cmd(mpi_tasks, verbose)

    sw4_mpi_run = mpirun_cmd + ' ' + sw4_exe
    #print('sw4_mpi_run = ', sw4_mpi_run)

    num_test=0
    num_pass=0
    num_fail=0

    all_dirs = ['meshrefine', 'meshrefine', 'meshrefine', 'attenuation', 'attenuation', 'pointsource', 'twilight', 'twilight', 'lamb']
    all_cases = ['refine-el', 'refine-att', 'refine-att-2nd', 'tw-att', 'tw-topo-att', 'pointsource-sg', 'flat-twi', 'gauss-twi', 'lamb']
    all_results =['TwilightErr.txt', 'TwilightErr.txt', 'TwilightErr.txt', 'TwilightErr.txt', 'TwilightErr.txt', 'PointSourceErr.txt', 'TwilightErr.txt', 'TwilightErr.txt', 'LambErr.txt']
    num_meshes =[1, 1, 1, 2, 1, 1, 2, 2, 1] # default number of meshes for level 0

    # add more tests for higher values of the testing level
    if testing_level == 1:
        num_meshes =[2, 2, 2, 3, 2, 2, 3, 3, 2]
    elif testing_level == 2:
        num_meshes =[2, 2, 2, 3, 3, 3, 3, 3, 3]
    
    print("Running all tests for level", testing_level, "...")
    # run all tests
    for qq in range(len(all_dirs)):
    
        test_dir = all_dirs[qq]
        base_case = all_cases[qq]
        result_file = all_results[qq]

        #make a local test directory
        if not os.path.exists(test_dir):
            os.mkdir(test_dir)

        os.chdir(test_dir) # change to the new local directory

        # put all test cases in a list and add a for loop for each test_dir
        for ii in range(num_meshes[qq]):
            num_test = num_test+1
        
            case_dir = base_case + '-' + str(ii+1)
            test_case = case_dir + '.in'
            print('Starting test #', num_test, 'in directory:', test_dir, 'with input file:', test_case)

            sw4_input_file = reference_dir + sep + test_dir + sep + test_case
            #print('sw4_input_file = ', sw4_input_file)

            sw4_stdout_file = case_dir + '.out'
            
            local_dir = pytest_dir + sep + test_dir
            #print('local_dir = ', local_dir)
    
            # pipe stdout and stderr to a temporary file
            run_cmd = mpirun_cmd.split() + [
                sw4_exe,
                sw4_input_file
            ]

            sw4_stdout_file = open(case_dir + '.out', 'wt')
            sw4_stderr_file = open(case_dir + '.err', 'wt')

            # run sw4
            run_dir = os.getcwd()
            #print('Running sw4 from directory:', run_dir)
            status = subprocess.run(
                run_cmd,
                stdout=sw4_stdout_file,
                stderr=sw4_stderr_file,
            )

            sw4_stdout_file.close()
            sw4_stderr_file.close()

            if status.returncode!=0:
                print('ERROR: Test', test_case, ': sw4 returned non-zero exit status=', status.returncode, 'aborting test')
                print('run_cmd=', run_cmd)
                print("DID YOU USE THE CORRECT SW4 EXECUTABLE? (SPECIFY DIRECTORY WITH -d OPTION)")
                return False # bail out

            ref_result = reference_dir + sep + test_dir + sep + case_dir + sep + result_file
            #print('Test #', num_test, 'output dirs: local case_dir =', case_dir, 'ref_result =', ref_result)

            # compare output (always compare the last line)
            success = compare_one_line(ref_result , case_dir + sep + result_file, 1e-5, 1e-10, -1, verbose)
            if success and 'attenuation' in test_dir:
                # also compare the 3rd last line in the files
                success = compare_one_line(ref_result , case_dir + sep + result_file, 1e-5, 1e-10, -3, verbose)
            if success:        
                print('Test #', num_test, "Input file:", test_case, 'PASSED')
                num_pass += 1
            else:
                print('Test #', num_test, "Input file:", test_case, 'FAILED')
                num_fail += 1
            
        # end for qq in all_dirs[qq]

        os.chdir('..') # change back to the parent directory

    # end for all cases in the test_dir
    print('Out of', num_test, 'tests,', num_pass, 'passed and', num_fail, 'failed.')
    # normal termination
    return True
    
#------------------------------------------------
if __name__ == "__main__":
    assert sys.version_info >= (3,5) # subprocess.run(...) requires 3.5
    # default arguments
    testing_level=0
    verbose=False
    mpi_tasks=0 # machine dependent default

    parser=argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("-l", "--level", type=int, choices=[0, 1, 2], 
                        help="testing level")
    parser.add_argument("-m", "--mpitasks", type=int, help="number of mpi tasks")
    parser.add_argument("-d", "--sw4_exe_dir", help="name of directory for sw4 executable", default="optimize")
    args = parser.parse_args()
    if args.verbose:
        #print("verbose mode enabled")
        verbose=True
    if args.level:
        #print("Testing level specified=", args.level)
        testing_level=args.level
    if args.mpitasks:
        #print("MPI-tasks specified=", args.mpitasks)
        if args.mpitasks > 0: mpi_tasks=args.mpitasks
    if args.sw4_exe_dir:
        #print("sw4_exe_dir specified=", args.sw4_exe_dir)
        sw4_exe_dir=args.sw4_exe_dir

    if not main_test(sw4_exe_dir, testing_level, mpi_tasks, verbose):
        print("test_sw4 was unsuccessful")

