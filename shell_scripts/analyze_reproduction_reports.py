import argparse
import csv
import os


def main(reproduction_csv):
    # reproduction_csv = 'logback-2021-05-13-report_total_reproduce.csv'
    test_to_max_fail_count = {}
    # Questions are: most and least reproducible, median and mean reproducibility, and proportion below 0.5
    # Here we assume the max is 100 for now.
    max_fail_count = 100
    rows_with_no_failure = set()
    with open(reproduction_csv) as reproduction_csv_fd:
        reproduction_csv_reader = csv.DictReader(reproduction_csv_fd)
        for row in reproduction_csv_reader:
            if row['FailCount'] == 'NoFail':
                rows_with_no_failure.add(tuple(row.values()))
                continue

            test_method = row['TestMethod']
            lines_to_sleep = row['SleepyLines']
            failure = row['Failure']
            minutes = row['Minutes']
            thread = row['Thread']
            key = tuple([test_method, thread, lines_to_sleep, failure, minutes])

            fail_count = int(row['FailCount'])

            previous_fail_count = test_to_max_fail_count.get(key, 0)
            if fail_count > previous_fail_count:
                test_to_max_fail_count[key] = fail_count

    # for key, fail_count in test_to_max_fail_count.items():
    #     print(f'{key},{fail_count}')

    print('Ones without a failure')
    print(rows_with_no_failure)

    report_name = f'{os.path.splitext(os.path.basename(reproduction_csv))[0]}_reproduction_analysis_report.csv'
    with open(report_name, 'w') as report_name_fd:
        report_name_fd.write("\"TestMethod\",\"Thread\",\"SleepyLines\",\"Failure\",\"Minutes\",\"MaxFailCount\"\n")
        for key, fail_count in test_to_max_fail_count.items():
            report_name_fd.write(f'\"{key[0]}\",\"{key[1]}\",\"{key[2]}\",\"{key[3]}\",\"{key[4]}\",\"{fail_count}\"\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("reproduction_data", help='results from reproduction_reports script in form of a csv')
    args = parser.parse_args()

    reproduction_data_path_arg = args.reproduction_data
    main(reproduction_data_path_arg)
