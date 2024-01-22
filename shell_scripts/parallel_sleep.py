import argparse
import csv
import datetime
import os
import subprocess
import stat

import boto3

date = datetime.datetime.now().strftime('%Y-%m-%d')


# noinspection SpellCheckingInspection
def main():
    """
    Uses nodes filepath to forward rows to do_remove_experiment on a remote node.
    :param test_methods_file_path:
    :param nodes_file_path:
    :param do_debug_logging:
    :return:
    """
    # Test ssh connection to every node if one doesn't work halt and yell about it.
    with open(nodes_file_path) as nodes_file_fd:
        for line in nodes_file_fd:
            node = line.strip()
            cmd_run = f'ssh -o ConnectTimeout=3 {node} \'echo $HOSTNAME\''
            try:
                subprocess.check_call(cmd_run, shell=True)
            except subprocess.SubprocessError as e:
                print(f'\'{cmd_run}\' failed')
                raise e

    parallel_root_path = 'parallel-work'
    os.system(f'mkdir -p {parallel_root_path}')

    parallel_log_path = os.path.join(os.getenv("FLAKY_HOME"), parallel_root_path, f'log-{run_identifier}.csv')
    parallel_argfile_path = os.path.join(parallel_root_path, f'parallel-argfile_{run_identifier}')

    with open(test_methods_file_path) as test_methods_fd:
        with open(parallel_argfile_path, 'w') as parallel_argfile_fd:
            dict_reader = csv.DictReader(test_methods_fd)
            for row in dict_reader:
                input_for_sleep = f"\"{row['Project_Git_URL']}\",\"{row['Git_SHA']}\",\"{row['TestMethod']}\" {run_identifier}"  # This is tied to do_remote_experiments
                dot_profile_cmd = '. .profile'
                do_remote_experiment_cmd = f"$PYTHON_FLAKY_BIN $FLAKY_HOME/shell_scripts/do_remote_experiment.py {input_for_sleep}"
                do_remote_sleep_cmd = f'{dot_profile_cmd} && {do_remote_experiment_cmd}'
                # do_remote_sleep_cmd = 'echo $HOSTNAME'  # Used for testing.
                parallel_argfile_fd.write(do_remote_sleep_cmd + '\n')

    # calls do_remote_experiment.py
    # We have -j1 to as we want to control threading on the remote machines.
    cmd_run = f'parallel --bar --results {parallel_log_path} --retries 5 --shuf -j1 --sshloginfile {nodes_file_path} :::: {parallel_argfile_path}'
    print('Doing Command \'{}\''.format(cmd_run))
    try:
        subprocess.check_call(cmd_run, shell=True)
        print('Finished Command \'{}\''.format(cmd_run))
        s3_key = f'{run_identifier}/{os.path.basename(parallel_log_path)}'

        session = boto3.Session(profile_name='flakyimpact')
        s3_client = session.client('s3')
        s3_client.upload_file(parallel_log_path, 'flakyimpact', s3_key)

    except subprocess.SubprocessError as e:
        print(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("testMethodsFile",
                        help="CSV containing rows with Project_Git_Url, Git_SHA, TestMethod")
    parser.add_argument("nodes_file",
                        help='The nodes to distribute Flake Rake work to.')
    parser.add_argument('--run_identifier')

    args = parser.parse_args()

    test_methods_file_path = args.testMethodsFile
    nodes_file_path = args.nodes_file
    run_identifier = args.run_identifier
    if not run_identifier:
        run_identifier = f'{os.path.basename(test_methods_file_path)}_{date}'
    else:
        run_identifier = f'{run_identifier}_{date}'
    main()
