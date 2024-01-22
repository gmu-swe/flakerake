import io
import socket
import sys
import run_experiments
import shutil
import csv
import subprocess
import os
import tempfile
import boto3

test_methods_file_row_str = sys.argv[1].strip()
run_identifier = sys.argv[2].strip()

print("Working on Linux node {} with run {}".format(socket.gethostname(), run_identifier))

if not os.path.exists(f'{os.environ.get("HOME")}/.aws/credentials'):
    raise FileNotFoundError('No AWS Credentials to use')

PYTHON_FLAKY_BIN = os.getenv('PYTHON_FLAKY_BIN')
FLAKY_HOME = os.getenv('FLAKY_HOME')

# Parse csv row from command argument
f = io.StringIO(test_methods_file_row_str)
csv_arg_reader = csv.reader(f, delimiter=',')
test_methods_file_rows = []
for row in csv_arg_reader:
    test_methods_file_rows.append(row)
if len(test_methods_file_rows) > 1:
    raise ValueError(f'More than one row in argument see {test_methods_file_rows}')

test_methods_file_row_parts = test_methods_file_rows[0]
test_methods_file_row_dict = {
    'Project_Git_URL': test_methods_file_row_parts[0],
    'Git_SHA': test_methods_file_row_parts[1],
    'TestMethod': test_methods_file_row_parts[2]
}

# Clone project and checkout SHA
try:
    install_options = run_experiments.install_options  # Get default install opts.

    # Special case builds
    project_git_url = test_methods_file_row_dict['Project_Git_URL']
    if 'httpcomponents-core' in project_git_url:
        # For okhttp we need it to work at all and for httpcomponents failures arent found due to it.
        newer_java_home = '/usr/lib/jvm/java-8-openjdk-amd64'
        os.environ['JAVA_HOME'] = newer_java_home
        os.environ['JAVA_FLAKY_HOME'] = newer_java_home

    if 'riptide' in test_methods_file_row_dict['Project_Git_URL']:
        riptide_opts = [
            '-Ddependency-check.skip',
            '-Djacoco.skip',
            '-Denforcer.skip'
        ]
        install_options = install_options + riptide_opts
    elif 'sawmill' in test_methods_file_row_dict['Project_Git_URL']:
        sawmill_opts = [
            '-Dgpg.skip',  # Sawmill, skip gpg signing
            '-Dmaven.antrun.skip'  # Sawmill, maybe special case? I don't think this will cause any problems
        ]
        install_options = install_options + sawmill_opts
    install_options_str = ' '.join(install_options)
    os.environ[run_experiments.install_opts_env_key] = install_options_str

    shutil.rmtree('experiment', ignore_errors=True)
    shutil.rmtree('.m2', ignore_errors=True)
    os.mkdir('experiment')

    # Install FlakeRake
    subprocess.run('mvn install -DskipTests', cwd=FLAKY_HOME, check=True, shell=True)

    subprocess.run(f"git clone {test_methods_file_row_dict['Project_Git_URL']}", shell=True, cwd='./experiment')
    project_dir = os.path.join(
        'experiment',
        os.path.basename(test_methods_file_row_dict['Project_Git_URL']).split('.git')[0])

    subprocess.run(f"git checkout {test_methods_file_row_dict['Git_SHA']} --force", shell=True, cwd=project_dir)

    if 'alluxio' in project_git_url:
        # Special case alluxio to use our provided pom.xml
        shutil.copyfile(
            os.path.join(
                os.getenv('FLAKY_HOME'),
                'shell_scripts', 'alluxio-modified-pom.xml'),
            f'{os.getenv("HOME")}/experiment/alluxio/pom.xml')

    if project_git_url == 'https://github.com/ninjaframework/ninja':
        # Special case Ninja as it has multiple controllers.ApplicationControllerTest test classes
        module_path_of_experiment = 'experiment/ninja/ninja-servlet-jpa-blog-integration-test'
    elif project_git_url == 'https://github.com/zxing/zxing':
        # Special case zxing as it has circular symlinks causing glob.glob to infinite loop
        # Note, we are special casing instead of a proper fix in order to reduce regression testing needs
        module_path_of_experiment = 'experiment/zxing/core'
    else:
        module_path_of_experiment = run_experiments.get_module_path(test_methods_file_row_dict['TestMethod'])
except subprocess.SubprocessError as e:
    print(e)
    raise e

with tempfile.NamedTemporaryFile(mode='w') as tmp_test_methods_fd:
    test_dict_writer = csv.DictWriter(tmp_test_methods_fd, fieldnames=test_methods_file_row_dict.keys())
    test_dict_writer.writeheader()
    test_dict_writer.writerow(test_methods_file_row_dict)
    tmp_test_methods_fd.flush()
    try:
        subprocess.check_call(f'{PYTHON_FLAKY_BIN} {FLAKY_HOME}/shell_scripts/findFlakySleeps.py ' +
                              f'--testMethodsFile {tmp_test_methods_fd.name} --runs 5',
                              cwd=module_path_of_experiment,
                              shell=True)
    except subprocess.SubprocessError as e:
        print(e)
        raise e

os.system('rm -f sleepy-records.zip')
shutil.make_archive('sleepy-records', 'zip', os.path.join(module_path_of_experiment, 'sleepy-records'))

# Upload zipped results to s3
github_url = test_methods_file_row_dict['Project_Git_URL']
project = '/'.join(github_url.split('/')[-2:]).split('.')[0]
s3_key = '/'.join([
    run_identifier,
    project,
    test_methods_file_row_dict['Git_SHA'],
    test_methods_file_row_dict['TestMethod'],
    'sleepy-records.zip'
])
session = boto3.Session(profile_name='flakyimpact')
s3_client = session.client('s3')
s3_client.upload_file('sleepy-records.zip', 'flakyimpact', s3_key)
