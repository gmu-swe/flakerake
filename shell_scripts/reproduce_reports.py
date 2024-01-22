import argparse
import csv
import os
import subprocess
import tempfile

import run_experiments


def main(all_reproduce_failure_file_path, num_runs=100, logging='info'):

    output_reproduction_report_accumulator_path = f'{os.path.splitext(os.path.basename(all_reproduce_failure_file_path))[0]}_total_reproduce'

    def setup_reproduction_run(reproduction_csv_dict_row):

        project_git_url = reproduction_csv_dict_row['Project_Git_URL']
        git_sha = reproduction_csv_dict_row['Git_SHA']
        test_method = reproduction_csv_dict_row['TestMethod']
        failure = reproduction_csv_dict_row['Failure']

        if failure == 'NoFail':
            return

        install_options = run_experiments.install_options  # Get default install opts.
        # Special case builds
        if 'httpcomponents-core' in project_git_url:
            # For okhttp we need it to work at all and for httpcomponents failures arent found due to it.
            newer_java_home = '/usr/lib/jvm/java-8-openjdk-amd64'
            os.environ['JAVA_HOME'] = newer_java_home
            os.environ['JAVA_FLAKY_HOME'] = newer_java_home

        if 'riptide' in project_git_url:
            riptide_opts = [
                '-Ddependency-check.skip',
                '-Djacoco.skip',
                '-Denforcer.skip'
            ]
            install_options = install_options + riptide_opts
        elif 'sawmill' in project_git_url:
            sawmill_opts = [
                '-Dgpg.skip',  # Sawmill, skip gpg signing
                '-Dmaven.antrun.skip'  # Sawmill, maybe special case? I don't think this will cause any problems
            ]
            install_options = install_options + sawmill_opts
        install_options_str = ' '.join(install_options)
        os.environ[run_experiments.install_opts_env_key] = install_options_str

        # Setup project
        subprocess.run('mkdir -p experiment', shell=True)
        subprocess.run(f'git clone {project_git_url}', shell=True, cwd='experiment')

        project_dir = os.path.join(
            'experiment',
            os.path.basename(project_git_url).split('.')[0]
        )

        subprocess.run(f"git checkout {git_sha}", shell=True, cwd=project_dir)

        module_path_of_experiment = run_experiments.get_module_path(test_method)
        with tempfile.NamedTemporaryFile(mode='w') as tmp_test_methods_fd:
            test_dict_writer = csv.DictWriter(tmp_test_methods_fd, fieldnames=reproduction_csv_dict_row.keys())
            test_dict_writer.writeheader()
            test_dict_writer.writerow(reproduction_csv_dict_row)
            tmp_test_methods_fd.flush()

            PYTHON_FLAKY_BIN = os.getenv('PYTHON_FLAKY_BIN')
            FLAKY_HOME = os.getenv('FLAKY_HOME')
            try:
                subprocess.check_call(f'{PYTHON_FLAKY_BIN} {FLAKY_HOME}/shell_scripts/findFlakySleeps.py ' +
                                      f'--reproduceFailureFile {tmp_test_methods_fd.name} --runs {num_runs}',
                                      cwd=module_path_of_experiment,
                                      shell=True)
                report_path = os.path.join(
                    module_path_of_experiment,
                    'sleepy-records',
                    'report',
                    f'{os.path.basename(tmp_test_methods_fd.name)}_reproduction_report.csv',
                )
                out_report_name = output_reproduction_report_accumulator_path
                subprocess.run(f'cat {report_path} >> {out_report_name}',
                               shell=True)

            except subprocess.SubprocessError as e:
                print(e)
                raise e

    with open(all_reproduce_failure_file_path) as all_reproduce_failure_file_fd:
        csv_dict_reader = csv.DictReader(all_reproduce_failure_file_fd)
        for row in csv_dict_reader:
            setup_reproduction_run(row)

    # We have to remove duplicate headers
    reproduction_report_lines = []
    with open(output_reproduction_report_accumulator_path) as output_reproduction_report_accumulator_fd:
        # Add initial csv header
        reproduction_report_lines.append(output_reproduction_report_accumulator_fd.readline())
        for line in output_reproduction_report_accumulator_fd:
            if 'Project_Git_URL' in line:
                # Skip all duplicate headers
                continue
    with open(f'{output_reproduction_report_accumulator_path}.csv', 'w') as output_reproduction_report_accumulator_csv_fd:
        output_reproduction_report_accumulator_csv_fd.writelines(reproduction_report_lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("reproduceFailureFile")
    parser.add_argument("--runs", default=100, type=int)
    args = parser.parse_args()

    reproduce_failure_file_path_arg = args.reproduceFailureFile
    num_runs_arg = args.runs
    main(reproduce_failure_file_path_arg, num_runs=num_runs_arg)
