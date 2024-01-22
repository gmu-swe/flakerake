import csv
import glob
import itertools
import subprocess
import time
from datetime import datetime
import os
import sys
import argparse


def get_module_path(test):
    test_parts = test.split('#')
    test_class = test_parts[0]
    test_class_top_class = test_class.split('$')[0]
    test_class_top_class = '/'.join(test_class_top_class.split('.'))
    test_src_filename_java = test_class_top_class + '.java'
    test_src_filename_groovy = test_class_top_class + '.groovy'

    print('Looking for path of ' + test_class_top_class)

    paths = glob.glob("**/{}".format(test_src_filename_java), recursive=True) + \
            glob.glob("**/{}".format(test_src_filename_groovy), recursive=True)

    if not paths:
        raise FileNotFoundError(test_class_top_class + '.[java or groovy]')

    if len(paths) > 1:
        print('WARNING found multiple paths for {}\n{}'.format(test_class_top_class, paths))

    # just chose the first one (Java) to break a tie.
    test_src_path = paths[0]
    idx_of_module = None
    for path in paths:
        try:
            # Try first success we can
            idx_of_module = path.rindex('/src')
            break
        except Exception as e:
            continue
    if not idx_of_module:
        raise Exception('Could not find /src in paths of {}'.format(paths))
    module_path = test_src_path[:idx_of_module]
    print('Found module path {} for test {}'.format(module_path, test))
    return module_path


install_options = [  # Default install opts
    '-DskipTests',  # Skip Tests when installing
    '-q',  # Quiet the log down
    '-B',  # Get rid of the escape keys
    '-fn',  # If a module fails just ignore in case we can still run the test
    '-s $FLAKY_HOME/shell_scripts/maven-repo-fix-settings.xml',  # So that Alluxio and Spring-Boot can fetch and install
    '-DskipITs'  # Skip ITs
]

install_opts_env_key = 'FLAKY_MVN_INSTALL_OPTS'
_install_options_str = ' '.join(install_options)
if install_opts_env_key not in os.environ:
    os.environ[install_opts_env_key] = _install_options_str


def install_project(path):
    """

    :param path: is an absolute path
    :return:
    """
    paths_to_install = []
    has_pom = True
    curr_path = path
    while os.path.realpath(curr_path) != '/':
        if os.path.exists(os.path.join(curr_path, 'pom.xml')):
            paths_to_install.append(curr_path)
        curr_path = os.path.split(curr_path)[0]

        # Edge case of reaching root dir
        if not curr_path:
            break

    print('Installing in ' + str(paths_to_install))

    while paths_to_install:
        try:
            # Special Case Google zxing to ignore zxingorg module mvn -pl '!zxingorg' install -DskipTests
            if paths_to_install[-1].endswith('zxing'):
                subprocess.check_call(f"mvn -pl '!zxingorg' install {os.environ[install_opts_env_key]}",
                                      shell=True,
                                      cwd=paths_to_install.pop(-1))
            elif paths_to_install[-1].endswith('handlebars.java'):
                subprocess.check_call(f"mvn -pl '!handlebars-proto' install {os.environ[install_opts_env_key]}",
                                      shell=True,
                                      cwd=paths_to_install.pop(-1))
            elif paths_to_install[-1].endswith('elastic-job-lite'):
                subprocess.check_call(f"mvn -pl '!elastic-job-lite-console' install {os.environ[install_opts_env_key]}",
                                      shell=True,
                                      cwd=paths_to_install.pop(-1))
            else:
                subprocess.check_call(f"mvn install {os.environ[install_opts_env_key]}",
                                      shell=True,
                                      cwd=paths_to_install.pop(-1))
        except subprocess.SubprocessError as e:
            print('Error running: ' + e.cmd)
            print(e.output)
            print(e)
            raise e
    

def install_sleepy_tool():
    subprocess.check_call('mvn install -DskipTests', shell=True, cwd=os.getenv('FLAKY_HOME'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--testMethodsFile",
                        help="Does minimal sleepy analysis using input path to csv file with columns Project, TestMethod, FirstFailingId, requires script to be run in project containing listed tests.",
                        required=True)
    parser.add_argument('--outputReportName',
                        help="What the name of the report file is",
                        default=None)
    parser.add_argument('--appendAWSFailures',
                        help="Appends the failure in flaky aws to the resulting table when doing a minimal sleepy line analysis. Default is True.",
                        default='True')

    parser.add_argument('--runs',
                        default='5')
    args = parser.parse_args()

    install_sleepy_tool()
    csv_path = args.testMethodsFile
    date = datetime.today().strftime('%Y-%m-%d')

    file = os.path.basename(csv_path)
    file_name = str(file.split(r'.')[0])

    begin_time = time.time()

    out_csv_name = '{}-experiment-{}.csv'.format(file_name,
                                                 date) if not args.outputReportName else args.outputReportName
    # Gather paths where we run the experiments
    module_to_input_rows = {}
    print('Working ' + csv_path)
    with open(csv_path, 'r') as flaky_csv_fd:
        row_dict_reader = csv.DictReader(flaky_csv_fd, dialect='unix')
        field_names = row_dict_reader.fieldnames
        for row in row_dict_reader:
            test_method = row['TestMethod']
            test_module_path = get_module_path(test_method)
            if test_module_path in module_to_input_rows:
                module_to_input_rows[test_module_path].append(row)
            else:
                module_to_input_rows[test_module_path] = [row]

    # Go ahead and write input csvs
    csv_filenames = []
    for path, rows in module_to_input_rows.items():
        csv_filename = os.path.basename(path) + '-{}.csv'.format(date)
        csv_filenames.append(csv_filename)
        csv_input_path = os.path.join(path, csv_filename)
        with open(csv_input_path, 'w') as csv_input_fd:
            flaky_csv_writer = csv.DictWriter(csv_input_fd, field_names)
            flaky_csv_writer.writeheader()
            flaky_csv_writer.writerows(rows)

    # Install every project
    for module_path in module_to_input_rows.keys():
        install_project(module_path)

    # Now run every experiment
    result_paths = []
    sha_to_stack_trace_paths = []
    for module_path, csv_name in zip(module_to_input_rows.keys(), csv_filenames):
        print("Running experiment in {} with input {}".format(module_path, csv_name))
        subprocess.check_call(
            '{} "$FLAKY_HOME/shell_scripts/findFlakySleeps.py" --testMethodsFile {} --runs {} --appendAWSFailures {}'
                .format(sys.executable,
                        csv_name,
                        args.runs,
                        args.appendAWSFailures),
            shell=True,
            cwd=module_path)

        report_dir = os.path.join(module_path, 'sleepy-records', 'report')
        result_paths.append(os.path.join(report_dir, csv_name + '_minimal_sleep_report.csv'))
        sha_to_stack_trace_paths.append(os.path.join(report_dir, csv_name + '_sha_to_stacktrace_report.csv'))

    # Read all results into a list
    results = []
    for path in result_paths:
        with open(path, 'r') as result_f:
            result_reader = csv.DictReader(result_f)
            results_field_names = result_reader.fieldnames
            for result in result_reader:
                results.append(result)

    # Now combine all the csv files into one super duper csv file.
    experiments_path = './{}'.format(out_csv_name)
    with open(experiments_path, 'w') as results_csv_f:
        results_writer = csv.DictWriter(results_csv_f, results_field_names)
        results_writer.writeheader()
        results_writer.writerows(results)

    end_time = time.time()
    minutes = (end_time - begin_time) // 60
    print('Finished - Wrote {} in {} minutes.'.format(experiments_path, minutes))
