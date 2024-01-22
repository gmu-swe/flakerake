import math
import os
import csv
import copy
import shutil
from os import path
import sys
import re
import subprocess
import time
import argparse
import logging
import socket
from enum import Enum

# Import FlakeRake things
import csv_utils
import run_experiments

minimalizing_method = 'bisection'

sleep_time_ms = 10000

no_sleep = False

LOGGING_LEVEL = None  # 'debug'

SLEEPY_TIMEOUT_FAIL_STR = 'SleepyTimeOut(ProbableDeadlock)'
FAILURE_THAT_COULD_NOT_BE_LOGGED = 'FAILURE_THAT_COULD_NOT_BE_LOGGED'

# The number of reruns to do before a flaky_fail_attempt or potential success depending on stable failure ratio.
NUM_TRIES = 5

STABLE_FAILURE_RATIO = 0.5

TEST_RUNNER = 'edu.gmu.swe.flaky.sleepy.runner.SleepyTestRunner'

project_argline = None

timeout_offset_ms = -1

max_test_method_analysis_time_ms = 24 * (60**2) * 1000  # 24 hours
max_test_method_analysis_time_ms_begin_time = None

# Java Debugging on or off.
DEBUG_CLIENT = "-agentlib:jdwp=transport=dt_socket,server=n,address=localhost:5005,suspend=y"
DEBUG_SERVER = "-agentlib:jdwp=transport=dt_socket,server=y,address=localhost:5005,suspend=y"
debug_arg = ''

# Check for environment variable setup.
if os.getenv('FLAKY_HOME') is None:
    print("Please set FLAKY_HOME env variable")
    exit(1337)

if os.getenv('MAVEN_REPO') is None:
    print("Please set MAVEN_REPO env")
    exit(1337)

if os.getenv('JAVA_FLAKY_HOME') is None:
    print('Please set JAVA_FLAKY_HOME')
    exit(1337)

# Instrumentation bootpath jar arg.
interceptor_jar_path = path.join(os.getenv('MAVEN_REPO'), 'edu/gmu/swe/flaky/sleepy/sleepy-interceptor/0.0.4-SNAPSHOT/sleepy-interceptor-0.0.4-SNAPSHOT.jar')
boot_clazz_path = interceptor_jar_path

test_method_to_sha_to_stacktrace_set = set()

sha_to_maximal_lines = {}

run_to_sha_to_maximal_lines = []

cause_to_interception = set()

test_method_to_sleepy_run_count = {}

minimal_exploration_report_set = set()
node_exploration_next_id = 1

JAVA_EXEC = os.path.join(os.getenv('JAVA_FLAKY_HOME'), 'bin', 'java')

# globals
clazz_path = None
test_method = None


def is_stable_failure(tId, runs, file_with_target_lines_to_slow=""):
    """
    Used to assess if a test how stable a flaky flaky_fail_attempt is
    :param tId: The identifier of the thread that's sleepy.
    :param file_with_target_lines_to_slow: File containing program lines of the form
    {Class}:{Method}:{LineNumber}
    :param runs: The number of times to run
    :return: String of failure if successfully stable, false otherwise.
    """
    # Clear flaky_fail_attempt file log
    if path.exists(path.join(INTERNAL_DIR, "failure.log")):
        os.remove(path.join(INTERNAL_DIR, "failure.log"))

    fail_count = 0
    for run in range(1, runs + 1):
        exit_code = do_run(tId, file_with_target_lines_to_slow)
        if exit_code != 0:
            fail_count += 1
        # Check if we've already satisfied stable failure or check if it's impossible. Keep this here for speed
        if is_stable_ratio(fail_count / runs):
            return get_failure_str()
        # Check if it's impossible for this to be a stable failure. Keep This here for speed.
        elif not is_stable_ratio((fail_count + (runs - run)) / runs):
            logging.info('Impossible to make stable failure so skipping {}'.format(tId))
            return False

    logging.info("Failure Ratio with tid:{} is {}/{}".format(tId, fail_count, runs))
    if is_stable_ratio(fail_count / runs):
        return get_failure_str() or 'FailureThatCouldntReadFromFailLog'
    else:
        logging.info('Unstable failure {}'.format(tId))
        return False


def setup(project_git_url, test_method_arg):
    """
    Sets various global variables and gets the classpath and other such.
    :param project_git_url:
    :param test_method_arg: Test method we're doing sleepy analysis on.
    """
    global clazz_path
    global test_method
    global project_argline
    global boot_clazz_path

    if LOGGING_LEVEL != 'debug':
        shutil.rmtree('./sleepy-records/internal', ignore_errors=True)
        os.mkdir('./sleepy-records/internal')

    test_method = test_method_arg
    print("Running " + test_method)
    # TODO test that this fails when mvn test fails instead of being ignored by -fn
    proc = subprocess.run(f"mvn test -X -Dtest={test_method} -DfailIfNoTests=false {os.environ[run_experiments.install_opts_env_key]}",
                          shell=True,
                          check=False,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          text=True)

    mvn_test_out = proc.stdout
    logging.info(f'{mvn_test_out}')
    proc.check_returncode()

    # We need to customize the jvm argLine because we never implemented this as a mojo (unforunately).
    argLine_regex_matches = re.findall(r'/*DEBUG.*argLine\s+=\s+(.+)', mvn_test_out)
    if len(argLine_regex_matches) > 1:
        raise ValueError(argLine_regex_matches)
    project_argline = argLine_regex_matches[0] if len(argLine_regex_matches) > 0 else ''
    logging.info(f'Found argLine:\'{project_argline}\'')

    # Setup classpath
    path_to_proj_clazz_path = path.join(INTERNAL_DIR, 'clazz_path.txt')
    try:
        proc = subprocess.run('mvn -fn dependency:build-classpath -s $FLAKY_HOME/shell_scripts/maven-repo-fix-settings.xml -Dmdep.outputFile=' + path_to_proj_clazz_path,
                              shell=True,
                              check=False,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              text=True)
        logging.info(f'{proc.stdout}')
        proc.check_returncode()
    except subprocess.CalledProcessError as e:
        print('Error running: ' + e.cmd)
        print(e.output)
        raise e
    with open(path_to_proj_clazz_path, 'r') as file:
        proj_clazz_path = file.read().replace('\n', '')

    sleepy_runner_jar_path = path.join(os.getenv('MAVEN_REPO'), 'edu/gmu/swe/flaky/sleepy/sleepy-runner/0.0.4-SNAPSHOT/sleepy-runner-0.0.4-SNAPSHOT.jar')
    clazz_path = '{}:./target/classes:./target/test-classes:{}'.format(proj_clazz_path, sleepy_runner_jar_path)
    # Special case for zxing because of where they put class files
    if 'zxing' in test_method_arg:
        clazz_path = f'{clazz_path}:./build'

    if '-cp' in project_argline:
        project_argline_cp_arg = re.findall(r'-cp\s+[^\s]+', project_argline)
        project_argline = project_argline.replace(project_argline_cp_arg[0], '')
        project_argline_cp_arg = re.findall(r'-cp\s+([^\s]+)', project_argline_cp_arg[0])
        if len(project_argline_cp_arg) != 1:
            raise ValueError(project_argline_cp_arg)
        project_argline_cp_arg = project_argline_cp_arg[0]
        clazz_path = f'{clazz_path}:{project_argline_cp_arg}'

    if '-Xbootclasspath/p:' in project_argline:
        project_argline_boot_cp_arg = re.findall(r'-Xbootclasspath/p:[^\s]+', project_argline)
        project_argline = project_argline.replace(project_argline_boot_cp_arg[0], '')
        project_argline_boot_cp_arg = re.findall(r'-Xbootclasspath/p:([^\s]+)', project_argline_boot_cp_arg[0])
        if len(project_argline_boot_cp_arg) != 1:
            raise ValueError(project_argline_boot_cp_arg)
        project_argline_boot_cp_arg = project_argline_boot_cp_arg[0]
        boot_clazz_path = f'{boot_clazz_path}:{project_argline_boot_cp_arg}'
        project_argline = project_argline.replace(project_argline_boot_cp_arg, '')


def do_run(tId_to_slow, file_with_target_lines_to_slow=""):
    """
    Note: There is a non-obvious special case here of tId_to_slow == 0, which doesn't do any slowing whatsoever since
    it does not match an existent threadID.
    We use this to get the various threads we should try slowing.
    TODO ^ Make this something more clear instead of 0.
    :param tId_to_slow: The identifier of the thread that we will give naps to.
    :param file_with_target_lines_to_slow: File containing program lines of the form
    {Class}:{Method}:{LineNumber}
    Where each one is a location where the thread argument will slow.
    :returns The exit code of running the test_method.
    """
    global last_err_code
    global timeout_offset_ms
    global test_method_to_sha_to_stacktrace_set
    global max_test_method_analysis_time_ms
    global project_argline
    global boot_clazz_path
    global sleep_time_ms
    global test_method_to_sleepy_run_count

    if file_with_target_lines_to_slow != "":
        key = tuple([test_method, tId_to_slow])
        run_count = test_method_to_sleepy_run_count.get(key, 0) + 1
        test_method_to_sleepy_run_count[key] = run_count

    # See if we need to fail early
    current_time_ms = time.time() * 1000
    time_spent_on_test_method_ms = (current_time_ms - max_test_method_analysis_time_ms_begin_time)
    if (time_spent_on_test_method_ms > max_test_method_analysis_time_ms):
        raise TimeoutError('No more time to study test method')

    if file_with_target_lines_to_slow:
        # Get maximum time to sleep for dynamic timeout calculations
        lines_to_intercept = set()
        with open(file_with_target_lines_to_slow) as file_with_target_lines_to_slow_fd:
            for line in file_with_target_lines_to_slow_fd.readlines():
                lines_to_intercept.add(line)

        max_time_added_per_interception = sleep_time_ms * math.ceil(math.log2(sleep_time_ms)) if sleep_time_ms > 0 else 0
        candidate_dynamic_timeout_ms = len(lines_to_intercept) * max_time_added_per_interception + timeout_offset_ms
        candidate_dynamic_timeout_ms += 10 * 60 * 1000  # Add 10 minutes for sanity sake.
    else:
        # If we're just running the test with no sleeping default to 1 hour.
        logging.info('Running test with no sleeping so using default sleep time.')
        candidate_dynamic_timeout_ms = 1.0 * (60**2) * 1000

    # Make either timeout either dynamic time or minimum of what we have available for the test method.
    dynamic_timeout_ms = min(candidate_dynamic_timeout_ms, max_test_method_analysis_time_ms - time_spent_on_test_method_ms)

    # Differentiate between timeout from likely deadlock or timeout from running out of time to analyze method.
    test_method_total_analysis_timeout = True if dynamic_timeout_ms != candidate_dynamic_timeout_ms else False

    instr_arg = '-XX:+ExitOnOutOfMemoryError -Xbootclasspath/p:{} -javaagent:{}'.format(boot_clazz_path, interceptor_jar_path)
    run = "{} {} {} {} -cp '{}' '{}' {} '{}' '{}' {} {}" \
        .format(JAVA_EXEC, instr_arg, project_argline, debug_arg, clazz_path, TEST_RUNNER, test_method, tId_to_slow,
                LOGGING_LEVEL,
                sleep_time_ms,
                file_with_target_lines_to_slow)
    logging.info('Using timeout {} minutes'.format(dynamic_timeout_ms // (60 * 1000)))
    logging.info("Running command:")
    logging.info(run)
    dynamic_timeout_sec = math.ceil(dynamic_timeout_ms / 1000)
    try:
        # Run the command with a timeout of an hour for live/deadlocks.
        proc = subprocess.run(run, shell=True, timeout=dynamic_timeout_sec, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # Kill off any Java processes hanging around - see orphaned processes in Java-WebSocket (they call it zombie).
        last_err_code = proc.returncode
        logging.info('====BEGIN Java Log====')
        logging.info(proc.stdout)
        logging.info('====END Java Log====')
        proc.check_returncode()
    except subprocess.TimeoutExpired as e:
        logging.info('Timeout flaky_fail_attempt')
        logging.info(e)

        if test_method_total_analysis_timeout:
            raise TimeoutError('No more time to study test method')

        with open(path.join(
                INTERNAL_DIR,
                "failure.log",
        ), 'w') as failure_file:
            failure_file.write(SLEEPY_TIMEOUT_FAIL_STR)
        return 1338

    except subprocess.SubprocessError as e:
        if (tId_to_slow == 0):
            print("Unable to get test to pass without any slowing, status:")
            print(e)
            print("====Stdout====")
            print(proc.stdout)
            print("====Stderr====")
            print(proc.stderr)
        logging.info('Non timeout flaky_fail_attempt')
        logging.info(e)
        failure_str = get_failure_str()
        if "NoFail" == failure_str:
            logging.error(e)
            with open(path.join(
                    INTERNAL_DIR,
                    "failure.log",
            ), 'w') as failure_file:
                failure_file.write(FAILURE_THAT_COULD_NOT_BE_LOGGED)
        return 1337
    except Exception as e:
        logging.warn(e)
        raise e
    finally:
        # Maintain table of SHA to StackTrace
        sha_to_stacktrace_path = os.path.join(INTERNAL_DIR, 'shaToStackTrace.csv')
        with open(sha_to_stacktrace_path) as sha_to_stacktrace_fd:
            reader = csv.reader(sha_to_stacktrace_fd)
            # There is no header for this temporary csv.
            for row in reader:
                test_method_to_sha_to_stacktrace_set.add(tuple([test_method] + row))
            os.remove(sha_to_stacktrace_path)

        cause_to_interception_path = os.path.join(INTERNAL_DIR, 'causeToInterception.csv')
        with open(cause_to_interception_path) as cause_to_interception_fd:
            reader = csv.reader(cause_to_interception_fd)
            # There is no header for this temporary csv.
            for row in reader:
                cause_to_interception.add(tuple([test_method, tId_to_slow, test_method_to_sleepy_run_count[key]] + row))
            os.remove(cause_to_interception_path)

        # Do below in case of hung orphaned processes
        subprocess.run('pkill --parent 1 java', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
        if 'linux' in sys.platform.lower():
            logging.info('Kill all Java processes')
            subprocess.run('killall -9 java', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

    # We don't currently do anything with exit codes besides check if zero or not.
    return 0


def threads_to_slow():
    """
    Gets every identifier for each thread. See SleepyInterceptor code for how this identifier is computed.
    :return sorted list of thread identifiers to attempt sleeping at areas of high contention.
    """
    global timeout_offset_ms
    failures = 0

    def update_maximal_thread_to_lines_map():
        global sha_to_maximal_lines
        with open(path.join(INTERNAL_DIR, 'sleepCalls.0')) as initialLogLinesfd:
            for line in initialLogLinesfd.readlines():
                logging.debug(line)
                items = line.split(":")
                # if items[0] == "true": # We want all lines that this thread would have reached.
                thread_sha = items[1]
                line = ":".join(items[2:])
                sha_to_maximal_lines[thread_sha] = sha_to_maximal_lines.get(thread_sha, [])  # Initialize
                if line not in sha_to_maximal_lines[thread_sha]:
                    sha_to_maximal_lines[thread_sha].append(line)

            run_to_sha_to_maximal_lines.append(copy.deepcopy(sha_to_maximal_lines))

    for attempt in range(NUM_TRIES):
        begin_time = time.time()
        global max_test_method_analysis_time_ms_begin_time
        max_test_method_analysis_time_ms_begin_time = begin_time * 1000
        exitCode = do_run(0)
        end_time = time.time()
        update_maximal_thread_to_lines_map()
        timeout_offset_ms += (end_time - begin_time) * 1000
        if exitCode != 0:
            logging.info("Unaltered flaky_fail_attempt: " + str(attempt + 1))
            failures += 1

    if is_stable_ratio(failures / NUM_TRIES):
        # If we cant even finish the tests, then we throw our hands up.
        logging.critical('Cannot successfully test without thread slowing.')
        raise Exception("Failure to successfully test without thread slowing.")

    out = list(sha_to_maximal_lines)
    out.sort()

    if not out:
        # Edge case for single threaded test that hit no interceptions
        sha_to_maximal_lines['<main>'] = ['NO_TARGET_HIT:NO_TARGET_HIT:NO_TARGET_HIT']
        out.append('<main>')

    for tId in out:
        logging.info("Found Thread {}".format(tId))
    return out


class MinimizingMethod(Enum):
    BISECTION = 1
    ONEBYONE = 2


def minimal_sleepy_lines(tId):
    return minimal_sleeps_method_function_map[minimalizing_method](tId)


def hard_code(tId):
    return [tuple(['I am a failure', ['hardcoded_clazz:hardcoded_method:hardcoded_number', 'hardcoded_clazz:hardcoded_method:hardcoded_number1']])]


def one_by_one(tId):
    return minimal_lines_helper(tId, MinimizingMethod.ONEBYONE)


def bisection_minimal_sleepy_lines(tId):
    return minimal_lines_helper(tId, MinimizingMethod.BISECTION)


def minimal_lines_helper(tId, mmethod):
    """
    :param tId: thread identifier
    :param mmethod: minimizing method
    :return: A list of tuple pairs of the form (failure, sleepylines),
        where each pair represents a failure and a set of minimal lines to sleep at to stably cause it.
    """
    # Read the sleepy log and create initial set of sleepy targets to do bisection.
    initialList = sha_to_maximal_lines[tId]

    logging.info("Initial list")
    logging.info(initialList)
    node_count = 0

    # Do initial sleep or root of sleep tree
    node_name = f'node-{test_method}-{node_count}'
    logging.debug(f'Working {node_name} (root sleep tree) with lines {initialList}')
    sleepy_path = path.join(INTERNAL_DIR, f"{node_name}.sleepList")
    with open(sleepy_path, 'w') as sleepy_node_f:
        sleepy_node_f.writelines(initialList)
    isa_stable_failure = is_stable_failure(tId, NUM_TRIES, file_with_target_lines_to_slow=sleepy_path)

    def track_node(failure, sleepy_lines):
        global node_exploration_next_id

        node_id = node_exploration_next_id
        node_exploration_next_id += 1
        timestamp = time.time()
        sleepy_lines_str = re.sub(r'\s+', '', ",".join(sleepy_lines))
        minimal_exploration_report_set.add(tuple([test_method, tId, sleepy_lines_str, failure, timestamp, node_id]))

    track_node(get_failure_str(), initialList)

    if not isa_stable_failure:
        logging.info(f'Could not fail {test_method} sleeping thread {tId}')
        return []

    failure_to_sleepy_lines = {}
    work_to_do = []

    def assoc_fail_with_sleepy_lines(failure, lines):
        logging.debug('Failure {} can be reproduced by lines of length {} that are {}'.format(failure, len(lines), lines))
        if failure in failure_to_sleepy_lines:
            failure_to_sleepy_lines[failure].append(lines)
        else:
            logging.debug('Found new failure {} with lines {}'.format(failure, lines))
            failure_to_sleepy_lines[failure] = [lines]

    def add_work_children(sleepy_lines):
        if mmethod is MinimizingMethod.BISECTION:
            if len(sleepy_lines) > 1:
                left_child = sleepy_lines[:len(sleepy_lines) // 2]
                right_child = sleepy_lines[len(sleepy_lines) // 2:]
                if left_child:
                    work_to_do.append(left_child)
                if right_child:
                    work_to_do.append(right_child)
        elif mmethod is MinimizingMethod.ONEBYONE:
            # Assumed to only be reached once when analyzing a thread.
            # Otherwise would be infinite
            for line in sleepy_lines:
                work_to_do.append([line])

    assoc_fail_with_sleepy_lines(get_failure_str(), initialList)
    add_work_children(initialList)

    logging.debug("Work to do:")
    logging.debug(f'{work_to_do}')

    # Here each node is a child of the initial list.
    try:
        while work_to_do:
            node_count += 1
            lines_to_try = work_to_do.pop(-1)
            node_name = f'node-{test_method}-{node_count}'
            logging.debug(f'Working {node_name} with lines {lines_to_try}')
            sleepy_path = path.join(INTERNAL_DIR, f"{node_name}.sleepList")
            with open(sleepy_path, 'w') as sleepy_node_f:
                sleepy_node_f.writelines(lines_to_try)
            stable_failure = is_stable_failure(tId, NUM_TRIES, file_with_target_lines_to_slow=sleepy_path)
            if stable_failure:
                stable_failure_str = get_failure_str()
                assoc_fail_with_sleepy_lines(stable_failure_str, lines_to_try)
                if stable_failure_str == SLEEPY_TIMEOUT_FAIL_STR:
                    logging.info(f'Recording {SLEEPY_TIMEOUT_FAIL_STR} with tid '
                                 f'{tId} and lines {lines_to_try}, skipping minimal analysis due to deadlock')
                elif mmethod is MinimizingMethod.BISECTION:
                    add_work_children(lines_to_try)
            track_node(get_failure_str(), lines_to_try)

    except TimeoutError:
        logging.warning(f'Stopping analysis after max analysis timeout on testmethod {test_method} '
                        f'giving partial results for thread {tId}')

    # Report unique failures and their minimum list of lines to reproduce.
    failure_min_lines_pairs = []
    for failure, lines_list in failure_to_sleepy_lines.items():
        min_len = sys.maxsize
        for lines in lines_list:
            if len(lines) < min_len:
                min_len = len(lines)
        for lines in lines_list:
            if len(lines) == min_len:
                failure_min_lines_pairs.append(tuple([failure, lines]))

    logging.debug('For thread {} minimal analysis returns {}'.format(tId, failure_min_lines_pairs))

    return failure_min_lines_pairs


def is_stable_ratio(failure_ratio):
    """
    :param failure_ratio: ratio of failures to total runs
    :return: Whether argument is high enough to call a flaky flaky_fail_attempt stable.
    """
    return failure_ratio > STABLE_FAILURE_RATIO


def reproduce_sleepy_run(thread, sleepy_lines):
    """
    :param thread: thread id to sleep
    :param sleepy_lines: list of lines to sleep thread id at
    :return whether we can stable reproduce the failure.
    """
    global test_method
    global NUM_TRIES
    # Create temporary file with sleepy_lines and call do_run with it and the tId
    reproduce_lines_path = path.join(INTERNAL_DIR, 'reproduce.tmp')
    with open(reproduce_lines_path, 'w') as reproduce_file:
        for line in sleepy_lines:
            reproduce_file.write(line + '\n')

    sample_count_failure_str_pairs = []
    for i in range(NUM_TRIES):
        logging.info(f'Reproducing: test={test_method} thread={thread}, sleepylines={sleepy_lines}, sample_idx={i}/{NUM_TRIES}')
        do_run(thread, reproduce_lines_path)
        sample_count_failure_str_pairs.append([i, get_failure_str()])

    return sample_count_failure_str_pairs
    # return is_stable_failure(thread, NUM_TRIES, reproduce_lines_path)


def find_all_naptime_lines():
    """
    :return: a list containing tuples of the form (Failure, {Lines need to sleep at to reproduce}, thread, minutes]
    """
    # Run slowing each thread id until finding one with a flaky_fail_attempt.
    out = []
    try:
        begin_time = time.time()
        unique_tids = threads_to_slow()
    except Exception as e:
        print(e)
        logging.warning(e)
        # Could not even pass successfully stably
        return [(get_failure_str(), "AlreadyFailsStably", "AlreadyFailsStably", (time.time() - begin_time) // 60)]

    tid_count = 0
    begin_time = time.time()
    global max_test_method_analysis_time_ms_begin_time
    max_test_method_analysis_time_ms_begin_time = begin_time * 1000
    try:
        for tId in unique_tids:
            tid_count += 1
            logging.info("Starting analysis on thread named {} that is {} out of {}".format(tId, tid_count, len(unique_tids)))

            if no_sleep:
                out.append(tuple([
                    'no_sleep_arg',
                    'no_sleep_arg',
                    tId,
                    'no_sleep_arg',
                ]))
                continue
            # full_analysis_filepath = path.join(INTERNAL_DIR, f"sleepCalls.{tId}")
            # stable_failure = is_stable_failure(tId, NUM_TRIES, full_analysis_filepath)

            # Stop and rerun single test method with more selective sleep lines.
            # Append the flaky_fail_attempt and a cutdown list of sleepy lines needed to reproduce.
            begin_time = time.time()
            fail_min_lines_pairs = minimal_sleepy_lines(tId)
            end_time = time.time()
            minutes = (end_time - begin_time) // 60
            if fail_min_lines_pairs:
                for failure, min_lines in fail_min_lines_pairs:
                    min_lines = re.sub(r'\s+', '', ",".join(min_lines))
                    out.append(tuple([failure, min_lines, tId, str(minutes)]))
            else:
                out.append(tuple(['NoFail', 'NoFail', tId, str(minutes)]))

            time_left_ms = (max_test_method_analysis_time_ms_begin_time + 1000 * 24 * 60**2) - time.time() * 1000
            time_left_minutes = time_left_ms // (1000 * 60)
            logging.info(f'After working thread {tId}, with {time_left_minutes} minutes left to analyze {test_method}')
    except TimeoutError:
        time_exceeded_msg = f'TestMethodAnalysisExceeded {max_test_method_analysis_time_ms / (1000 * 60 ** 2)} Hours'
        logging.warning(time_exceeded_msg)
        out.append(tuple([time_exceeded_msg, time_exceeded_msg, tId, time_exceeded_msg]))
    return out


def get_failure_str():
    # Note: this refers to the failure.log file which is used by each run.
    # This function returns the most recent failure.

    if not path.exists(path.join(INTERNAL_DIR, "failure.log")):
        return "NoFail"
    with open(path.join(INTERNAL_DIR, "failure.log"), "r") as failure_file:
        failure_str = failure_file.read()
        logging.debug("Failure from " + test_method)
        logging.debug(failure_str)

        if failure_str == SLEEPY_TIMEOUT_FAIL_STR or failure_str == FAILURE_THAT_COULD_NOT_BE_LOGGED:
            # Since the generator will remove the sleepy timeout string (does not match a package prefix)
            # We need to return it now.
            return failure_str

        failure_str_parts = failure_str.partition('\n')

        failure_exception_line = failure_str_parts[0]
        failure_rest = failure_str_parts[2]

        # Sanitize into ascii
        failure_exception_line = failure_exception_line.encode('ascii', errors='backslashreplace').decode('ascii')
        failure_rest = failure_rest.encode('ascii', errors='backslashreplace').decode('ascii')

        failure_rest_base64 = csv_utils.flake_rake_base64_encode(failure_rest)
        failure_str = f'{failure_exception_line}FlakeRakeB64StackTrace={failure_rest_base64}'

        # Handle if we dont find anything.
        if failure_str.strip() == "":
            failure_str = "NoFail"
    return failure_str


REPORT_DIR = './sleepy-records/report'
INTERNAL_DIR = './sleepy-records/internal'
LOG_DIR = './sleepy-records/logs'


def create_dirs():
    # Remove old logs and internal directory if present
    shutil.rmtree('./sleepy-records/internal', ignore_errors=True)
    shutil.rmtree('./sleepy-records/logs', ignore_errors=True)

    subprocess.check_call('mkdir -p ./sleepy-records', shell=True)
    subprocess.check_call('mkdir -p ./sleepy-records/report/', shell=True)
    subprocess.check_call('mkdir -p ./sleepy-records/internal/', shell=True)
    subprocess.check_call('mkdir -p ./sleepy-records/logs/', shell=True)


def do_mvn_install():
    logging.info(f'Installing project with mvn opts=\'{os.environ[run_experiments.install_opts_env_key]}\'')
    run_experiments.install_project(os.getcwd())


# Register minimalizaiton method here.
minimal_sleeps_method_function_map = {'bisection': bisection_minimal_sleepy_lines, 'hardcoded': hard_code, 'onebyone': one_by_one}

if __name__ == '__main__':
    script_begin_time = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--testMethodsFile",
        help="Does minimal sleepy analysis using input path to csv file with columns Project, TestMethod, FirstFailingId, requires script to be run in project containing listed tests.",
        default="")
    parser.add_argument(
        "--reproduceFailureFile",
        help="Deprecated: Reproduces sleepy failure using input path to csv file with columns TestMethod, Thread, SleepyLines, requires script to be run in project containing listed tests.",
        default="")
    parser.add_argument("--runs", help="Number of runs to try to make a flaky failure stable, a stable failure must be > 1/2 runs. Default is 5.", default="5")
    parser.add_argument("--debug", help="Java debug argument [server|client] Server blocks util you connect and client autoconnects to debug server.", default="")
    parser.add_argument('--logging', help="[info | debug | critical]. Default is info.", default="info")
    parser.add_argument('--no_sleep', help="Do no sleepy analysis, just runs with instrumentation - used for debugging", action='store_true')
    parser.add_argument('--minimalizing_method', help=f"Method for minimalizing sleepy lines to reproduce a failure. Default is `{minimalizing_method}`", default=minimalizing_method)
    parser.add_argument('--sleep_time_ms', help=f"Initial time (ms) for FlakeRake to sleep at its chosen lines. Default is `{sleep_time_ms}`", default=sleep_time_ms, type=int)
    args = parser.parse_args()

    no_sleep = args.no_sleep
    sleep_time_ms = args.sleep_time_ms

    create_dirs()

    LOGGING_LEVEL = args.logging
    # Copied from pydoc.
    LEVELS = {'debug': logging.DEBUG, 'info': logging.INFO, 'warning': logging.WARNING, 'error': logging.ERROR, 'critical': logging.CRITICAL}

    # Note this overwrites the previous logfile.
    logging.basicConfig(filemode='w', filename=path.join(LOG_DIR, 'sleepy-script.log'), level=LEVELS.get(LOGGING_LEVEL))

    logging.info('Beginning Script')
    logging.info(f'On host \'{socket.gethostname()}\'')

    logging.info(f'Using options {args}')
    logging.info(f'FlakeRakeStartTime={time.time()}')

    proc = subprocess.run('git rev-parse HEAD', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    logging.info(f'(git rev-parse HEAD)={proc.stdout}')

    NUM_TRIES = int(args.runs)

    if args.debug == "server":
        debug_arg = DEBUG_SERVER
    elif args.debug == "client":
        debug_arg = DEBUG_CLIENT

    # Check for mutually exclusive arguments.
    if args.reproduceFailureFile and args.testMethodsFile:
        print('Please select reproduceFailureFile xor testMethodsFile ... not both')
        exit(1)

    # set minimalizing method
    minimalizing_method = args.minimalizing_method
    if minimalizing_method not in minimal_sleeps_method_function_map:
        raise ValueError(f'Unrecognized SleepyLines Minimalized Method {minimalizing_method}'
                         f'\nOptions are: {list(minimal_sleeps_method_function_map.keys())}')

    logging.info(f'Using Sleepylines minimalizing method {minimalizing_method}')

    do_mvn_install()
    print("Install completed")

    # Check if we should reproduce first
    if args.reproduceFailureFile != "":
        reproduceFailPath = path.join(args.reproduceFailureFile)
        reproduction_output_report_path = path.join(REPORT_DIR, path.basename(reproduceFailPath) + '_reproduction_report.csv')
        with open(reproduction_output_report_path, 'w') as reproduction_output_report_path_report_fd:
            reproduction_fields = ['Project_Git_URL', 'Git_SHA', 'TestMethod', 'Thread', 'SleepyLines', 'SampleIdx', 'Failure', 'Seconds']
            reproduction_writer = csv.DictWriter(reproduction_output_report_path_report_fd, reproduction_fields, dialect='unix')
            reproduction_writer.writeheader()
            with open(reproduceFailPath, encoding='utf-8-sig') as input_file_fd:
                row_dict_reader = csv.DictReader(input_file_fd)
                for row in row_dict_reader:
                    test_method = row['TestMethod']
                    git_sha = row.get('Git_SHA', 'NO_GIT_SHA')
                    project_git_url = row.get('Project_Git_URL', 'No Project_Git_URL')
                    thread = row['Thread']
                    sleepLines = row['SleepyLines'].split(',')

                    logging.info('Attempting to reproduce {} sleeping {} at {}'.format(test_method, thread, sleepLines))

                    setup(project_git_url, test_method)
                    test_package_prefix = '.'.join(test_method.split(r'.')[0:2])
                    if test_package_prefix == test_method:
                        # Special case packages where the prefix is of length 1.
                        test_package_prefix = test_method.split(r'.')[0]

                    begin_time = time.time()
                    max_test_method_analysis_time_ms = float(row['Minutes']) * 60 * 1000 * NUM_TRIES
                    max_test_method_analysis_time_ms_begin_time = time.time() * 10000
                    attempt_out = reproduce_sleepy_run(thread, sleepLines)
                    end_time = time.time()
                    seconds = (end_time - begin_time)

                    for sample_index, failure_str in attempt_out:
                        row = {
                            'Project_Git_URL': project_git_url,
                            'Git_SHA': git_sha,
                            'TestMethod': test_method,
                            'Thread': thread,
                            'SleepyLines': ','.join(sleepLines),
                            'SampleIdx': str(sample_index),
                            'Failure': failure_str,
                            'Seconds': str(seconds),
                        }
                        reproduction_writer.writerow(row)
                    reproduction_output_report_path_report_fd.flush()  # Flush in case of failure.

        print("Sleepy reproduction report is in {}".format(reproduction_output_report_path))
    # Check if we should get all the different lines
    elif args.testMethodsFile != "":
        test_method_filepath = path.join(args.testMethodsFile)

        report_destination_path = path.join(REPORT_DIR, path.basename(test_method_filepath) + '_minimal_sleep_report' + ".csv")

        minimal_sleepy_analysis_fields = ['Project_Git_URL', 'Git_SHA', 'TestMethod', 'Minutes', 'Thread', 'SleepyLines', 'Failure']
        with open(report_destination_path, "w") as out:

            csv_report_writer = csv.DictWriter(out, minimal_sleepy_analysis_fields, dialect='unix')
            csv_report_writer.writeheader()

            with open(test_method_filepath, encoding='utf-8-sig') as test_method_file:
                # Assumes we have headers to act as keys
                row_dict_reader = csv.DictReader(test_method_file, dialect='unix')
                for row in row_dict_reader:
                    # Get project   test_method   flaky_log_id
                    project = row.get('Project_Git_URL', 'No Project_Git_URL')
                    test_method = row['TestMethod']
                    git_sha = row.get('Git_SHA', 'NO_GIT_SHA')

                    logging.info("Thread Sleeping analysis on " + test_method)

                    test_package_prefix = '.'.join(test_method.split(r'.')[0:2])
                    if test_package_prefix == test_method:
                        # Special case packages where the prefix is of length 1.
                        test_package_prefix = test_method.split(r'.')[0]

                    setup(project, test_method)

                    # Minimal list contains a list of tuples of the form..
                    # failure string, shrinked list of lines to sleepy to reproduce, thread, minutes
                    minimal_list = find_all_naptime_lines()
                    logging.info(minimal_list)

                    # Write rows
                    for flaky_fail_attempt in minimal_list:
                        failure_str = flaky_fail_attempt[0]  # Actual failure found.
                        minimal_list_str = flaky_fail_attempt[1]  # list of lines to reproduce flaky failure
                        flaky_thread = flaky_fail_attempt[2]  # Thread id we found failure with.
                        minutes = flaky_fail_attempt[3]

                        record = {
                            'Project_Git_URL': project,
                            'Git_SHA': git_sha,
                            'TestMethod': test_method,
                            'Minutes': minutes,
                            'Thread': flaky_thread,
                            'SleepyLines': minimal_list_str,
                            'Failure': failure_str
                        }

                        logging.debug('Writing Row {}'.format(record))

                        csv_report_writer.writerow(record)

                        out.flush()  # Flush the report so if we get a flaky_fail_attempt we have at least some data.

        with open(os.path.join(REPORT_DIR, '{}_sha_to_stacktrace_report.csv'.format(path.basename(test_method_filepath))), 'w') as sha_to_stacktrace_report_fd:
            csv_sha_stacktrace_writer = csv.writer(sha_to_stacktrace_report_fd, dialect='unix')
            sha_to_stacktrace_fields = ['TestMethod', 'Thread', 'StackTrace']
            csv_sha_stacktrace_writer.writerow(sha_to_stacktrace_fields)
            csv_sha_stacktrace_writer.writerows(test_method_to_sha_to_stacktrace_set)

        with open(os.path.join(REPORT_DIR, '{}_cause_to_interception_report.csv'.format(path.basename(test_method_filepath))), 'w') as cause_to_interception_report_fd:
            csv_cause_interception_writer = csv.writer(cause_to_interception_report_fd, dialect='unix')
            cause_to_interception_fields = ['TestMethod', 'Thread', 'SleepyRunId', 'Cause', 'Interception', 'HitSleepCount', 'CumulativeSleepTimeMS']
            csv_cause_interception_writer.writerow(cause_to_interception_fields)
            csv_cause_interception_writer.writerows(cause_to_interception)

        with open(os.path.join(REPORT_DIR, f'{test_method_filepath}_minimal_exploration_report.csv'), 'w') as minimal_exploration_report_fd:
            csv_minimal_exploration_writer = csv.writer(minimal_exploration_report_fd, dialect='unix')
            minimal_exploration_fields = ['TestMethod', 'Thread', 'SleepyLines', 'Failure', 'EpochSeconds', 'GlobalExploreID']
            csv_minimal_exploration_writer.writerow(minimal_exploration_fields)
            csv_minimal_exploration_writer.writerows(minimal_exploration_report_set)

        with open(os.path.join(REPORT_DIR, f'{test_method_filepath}_init_api_interceptions.csv'), 'w') as init_api_interceptions_fd:
            csv_init_api_interceptions_writer = csv.writer(init_api_interceptions_fd, dialect='unix')
            csv_init_api_interceptions_writer_fields = ['initialRun', 'Thread', 'sleepyline']
            csv_init_api_interceptions_writer.writerow(csv_init_api_interceptions_writer_fields)
            for idx, sha_to_sline_map in enumerate(run_to_sha_to_maximal_lines):
                for sha, slines in sha_to_sline_map.items():
                    for sline in slines:
                        row = [idx, sha, sline.strip()]
                        csv_init_api_interceptions_writer.writerow(row)

        print("Sleepy analysis report is in {}".format(report_destination_path))
    else:
        raise Exception('No argument given.')

    script_end_time = time.time()
    script_minutes = (script_end_time - script_begin_time) // 60
    logging.info(f'FlakeRake in total took {script_minutes} minutes.')
    logging.info(f'FlakeRakeEnd={time.time()}')
    logging.info('Ending Script')
