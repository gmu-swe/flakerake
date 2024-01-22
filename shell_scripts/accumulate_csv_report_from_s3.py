import argparse
import os
import subprocess
import zipfile
import shutil
from time import sleep

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parses through all of the reports for a flake rake parallel job '
                                                 'in s3://flakyimpact and accumulates them')
    parser.add_argument("run_identifier", help='The flakerake parallel run identifier '
                                               'to get reports from s3 '
                                               '- these are also the keys in s3://flakyimpact')
    parser.add_argument("--no_cleanup", action='store_true')
    args = parser.parse_args()

    run_identifier = args.run_identifier
    no_cleanup = args.no_cleanup

    tmp_dir = 'tmp-aws'
    if os.path.exists(tmp_dir):
        print(f'About to remove {tmp_dir}')
        sleep(2)
    subprocess.check_call('mkdir -p tmp-aws', shell=True)

    cmd = f'aws --profile flakyimpact s3 sync s3://flakyimpact/{run_identifier} .'
    subprocess.check_call(cmd, shell=True, cwd=tmp_dir)
    report_types = [
        '_minimal_sleep_report.csv',
        '_cause_to_interception_report.csv',
        '_sha_to_stacktrace_report.csv'
    ]

    output_dir = f"./{run_identifier}_reports"
    os.makedirs(output_dir, exist_ok=True)

    def write_cumulative_report(report_type_suffix):
        output_csv = f'{output_dir}/{run_identifier}{report_type_suffix}'
        wrote_header = False
        with open(output_csv, 'w') as output_csv_fd:
            for dirpath, dirs, files in os.walk(tmp_dir):
                for file in files:
                    file = os.path.join(dirpath, file)
                    if zipfile.is_zipfile(file):
                        with zipfile.ZipFile(file) as sleepy_records_zip:
                            minimal_list_report = None
                            for member in sleepy_records_zip.namelist():
                                if member.endswith(report_type_suffix):
                                    minimal_list_report = member

                            minimal_list_report_bytes = sleepy_records_zip.read(minimal_list_report)
                            minimal_list_report_string = minimal_list_report_bytes.decode('utf-8')
                            past_header = False
                            for line in minimal_list_report_string.splitlines():
                                if wrote_header and not past_header:
                                    past_header = True
                                    continue
                                else:
                                    wrote_header = True
                                output_csv_fd.write(line)
                                output_csv_fd.write('\n')

    for report_type in report_types:
        write_cumulative_report(report_type)

    if not no_cleanup:
        shutil.rmtree(tmp_dir)
