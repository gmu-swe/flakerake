import csv
import glob
import time
from datetime import datetime
import argparse
import os
import subprocess

vms = []


def vms_copy_combine(filepath, out_combined_report_name):
    filenames = []
    for vm in vms:
        filename = '{}-{}'.format(vm, os.path.basename(filepath))
        filenames.append(filename)
        cmd_copy = "rsync -zPa {}:{} ./{}".format(vm, filepath, filename)
        print('Doing Command \'{}\''.format(cmd_copy))
        subprocess.check_call(cmd_copy, shell=True)

    def combine_csvs(out_name):
        csv_rows = []
        header = None
        for name in filenames:
            with open(name, 'r') as path_fd:
                row_dict_reader = csv.DictReader(path_fd, dialect='unix')
                header = row_dict_reader.fieldnames
                for row in row_dict_reader:
                    csv_rows.append(row)
        with open(out_name, 'w') as out_name_fd:
            row_dict_writer = csv.DictWriter(out_name_fd, header)
            row_dict_writer.writeheader()
            row_dict_writer.writerows(csv_rows)

        print('Wrote {}'.format(out_name))

    combine_csvs(out_combined_report_name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--testMethodsFile",
                        help="Does minimal sleepy analysis using input path to csv file with columns Project, "
                             "TestMethod, FirstFailingId, requires script to be run in project containing listed "
                             "tests.",
                        required=True)
    parser.add_argument("--awsArchive",
                        help='AWS archive to rsync over',
                        required=True)
    parser.add_argument("--experiment",
                        help='Project we are experimenting on',
                        required=True)
    parser.add_argument("--nodesfile",
                        help='The hosts to distribute the work to via ssh',
                        required=True)
    args = parser.parse_args()
    #
    begin_time = time.time()

    vms = []
    with open(args.nodesfile, 'r') as nodesfile_fd:
        lines = nodesfile_fd.readlines()
        for line in lines:
            vms.append(line.strip())

    for vm in vms:
        cmd_aws = "rsync -zPa {} {}:~/flaky-test-aws/".format(args.awsArchive, vm)
        print('Doing Command \'{}\''.format(cmd_aws))
        subprocess.check_call(cmd_aws, shell=True)

        cmd_experiment = "rsync -zPa {} {}:~/flaky-impact/experiments/".format(args.experiment, vm)
        print('Doing Command \'{}\''.format(cmd_experiment))
        subprocess.check_call(cmd_experiment, shell=True)

    date = datetime.today().strftime('%Y-%m-%d')
    # calls do_remote_experiment pyscript.
    cmd_run = 'cat {} | parallel --sshloginfile {} --header : "source '.format(args.testMethodsFile, args.nodesfile) + \
              r'.profile; \$FLAKY_HOME/do_remote_experiment {}' + ' {}"'.format(
        date)  # Here the 2nd to last {} is reserved on purpose for parallel.
    print('Doing Command \'{}\''.format(cmd_run))
    subprocess.check_call(cmd_run, shell=True)
    out_report_name = '{}-{}.csv'.format(os.path.basename(args.testMethodsFile).split('.')[0], date)
    total_report = 'total_report-{}.csv'.format(date)
    vms_copy_combine('/home/cc/flaky-impact/{}'.format(total_report), out_report_name)

    end_time = time.time()
    minutes = (end_time - begin_time) // 60
    print("Time to do multi sleep {} minutes".format(minutes))
