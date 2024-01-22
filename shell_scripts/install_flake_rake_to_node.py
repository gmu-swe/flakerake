import os
import subprocess
import tempfile
import concurrent.futures
import argparse

include_list = [
    'shell_scripts**',
    'sleepy-parent**',
    'jdk-8u102.tgz',
    'pom.xml',
    'README.md',
]

remote_flaky_home = '~/flaky-impact'

rsync_timeout_seconds = 10

def copy_flake_rake(node):
    with tempfile.NamedTemporaryFile(mode='w') as tmp_fd:
        tmp_fd.write('\n'.join(include_list))
        tmp_fd.flush()
        cmd = f"rsync --timeout={rsync_timeout_seconds} -e \"ssh -o StrictHostKeyChecking=no\" -v -zPa --include-from={tmp_fd.name} --exclude '**' ./ {node}:{remote_flaky_home}"
        print('Doing Command {} on {}.'.format(cmd, node))
        try:
            subprocess.check_call(cmd, shell=True, cwd=os.environ['FLAKY_HOME'], stdout=subprocess.PIPE)
            print('Finished Command \'{}\' in flaky-impact home.'.format(cmd))
        except subprocess.SubprocessError as e:
            print(f'{e} with cmd=\'{cmd}\'')


def install_flake_rake(node):
    copy_flake_rake(node)
    cmd = f"ssh -t  -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {node} " \
          f"\"export FLAKY_HOME={remote_flaky_home} && bash {remote_flaky_home}/shell_scripts/node-install-deps\""
    print('Doing Command {} on {}.'.format(cmd, node))
    try:
        subprocess.check_call(cmd, shell=True, cwd=os.environ['FLAKY_HOME'])
        print('Finished installing {} on {}.'.format(cmd, node))
    except subprocess.SubprocessError as e:
        print(f'{e} with cmd=\'{cmd}\'')


def copy_flake_rake_parallel(nodes):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for node in nodes:
            executor.submit(copy_flake_rake, node)


def install_flake_rake_parallel(nodes):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for node in nodes:
            executor.submit(install_flake_rake, node)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("nodes_file",
                        help="A file containing a newline separated list of nodes to copy and or install to")
    parser.add_argument("--no_install",
                        help="Does not install, only copies files over.",
                        action='store_true',
                        default=False)
    parser.add_argument("--remote_flaky_home",
                        default="~/flaky-impact",
                        help="Where Flake Rake should be installed on the remote machine.")

    args = parser.parse_args()
    nodes_file_path = args.nodes_file
    no_install_bool = args.no_install
    global remote_flaky_home
    remote_flaky_home = args.remote_flaky_home

    nodes_to_work = []
    with open(nodes_file_path) as nodes_file_fd:
        for line in nodes_file_fd:
            if line.startswith('#'):
                continue
            nodes_to_work.append(line.strip())

    if no_install_bool:
        copy_flake_rake_parallel(nodes_to_work)
    else:
        install_flake_rake_parallel(nodes_to_work)


if __name__ == '__main__':
    main()
