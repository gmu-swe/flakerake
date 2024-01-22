import os
import glob

import subprocess as sp

import getpass

import multiprocessing as mp

import pandas as pd

import shutil

pd.set_option('display.max_columns', None)

# pd.set_option('display.max_rows', None)

# tar --extract --file=$target -C tmp sleepy-records/report/reproduce.csv_reproduction_report.csv

# For each, unzip and then grab

abstract_sline_causes = [
    "FLAGGED_API",
    "RUNNABLE_CALLABLE_START",
    "SYNCHRONIZED_METHOD_ENTER",
    "SYNCHRONIZED_METHOD_EXIT",
    "MONITORENTER",
    "MONITOREXIT",
]

ENDED_EARLY = "TestMethodAnalysisExceeded 24.0 Hours"

OBO = 'OBO'
BIS = 'BIS'

MAIN = '<main>'

report_cause_interception = 'flakeRakeInput.csv_cause_to_interception_report.csv'
report_minimal_exploration = 'flakeRakeInput.csv_minimal_exploration_report.csv'
report_minimal_sleep = 'flakeRakeInput.csv_minimal_sleep_report.csv'
report_sha_stacktrace = 'flakeRakeInput.csv_sha_to_stacktrace_report.csv'

# test_path = '/Users/aaron/code/flaky-impact/experiments/logback/logback-classic/rerun_vary_time/1642134418.995061'

aaron_flake_rake = '/Users/aaron/code/flake-rake'
logs_path = f'{aaron_flake_rake}/mock-flakerake-logs/final'
scratch = f'{aaron_flake_rake}/scratch'
matched_failures_slines = f'{aaron_flake_rake}/matched-failures-all-sleepy-lines.csv'
matched_failures = f'{aaron_flake_rake}/matched-failures.csv'
output_dir = scratch

if getpass.getuser() == 'flakerake':
    logs_path = '/experiment/flakerake/final-results/detect-results'
    scratch = '/scratch'
    matched_failures_slines = '/experiment/flakerake/final-results/matched-failures-all-sleepy-lines.csv'
    matched_failures = '/experiment/flakerake/final-results/matched-failures.csv'
    output_dir = '/experiment/flakerake/characteristics-5000'

tmp_dir = f'{scratch}/accum-tmp'

use_preprocessed = False

preprocessed_out_df = None
preprocessed_skip_df = None

if use_preprocessed:
    preprocessed_out_df = './characteristics/flakerake-thread-lines-meta-next.csv'
    preprocessed_skip_df = './characteristics/thread-skipped.csv'


def write_csv(df, path, index=False):
    print(f'Writing: {path}')
    df.to_csv(path, index=index)


# def get_unpacked_matched_failures():
#     global matched_failures_slines

#     df = df[[  # 'failureID',
#         'test',
#         'failureMessage',
#         'failureID',
#         'FailConfigs.flakerake',
#         'FailConfigs.flakerake-obo',
#     ]]
#     df = df.reset_index()
#     df['matchedIdx'] = df.index

#     out = pd.DataFrame(columns=[
#         'matchedIdx',
#         'Thread.BIS',
#         'SleepyLines.BIS',
#         'Thread.OBO',
#         'SleepyLines.OBO',
#     ])

#     bis_rows = []
#     obo_rows = []
#     for idx, row in df.iterrows():
#         print(f'Did {idx}/{len(df)}')
#         has_flakerake_config = False

#         out_row = None

#         if not pd.isna(row['FailConfigs.flakerake']):
#             has_flakerake_config = True
#             for config in row['FailConfigs.flakerake'].split(';'):
#                 out_row = {
#                     'matchedIdx': idx,
#                 }
#                 thread = config.split(' ')[0]
#                 slines = config.split(' ')[1]
#                 out_row['Thread.BIS'] = thread
#                 out_row['SleepyLines.BIS'] = slines
#                 bis_rows.append(out_row)

#         if not pd.isna(row['FailConfigs.flakerake-obo']):
#             has_flakerake_config = True
#             for config in row['FailConfigs.flakerake-obo'].split(';'):
#                 out_row = {
#                     'matchedIdx': idx,
#                 }
#                 thread = config.split(' ')[0]
#                 slines = config.split(' ')[1]
#                 out_row['Thread.OBO'] = thread
#                 out_row['SleepyLines.OBO'] = slines
#                 obo_rows.append(out_row)

#         if has_flakerake_config:
#             out = out.append(out_row, ignore_index=True)

#     bis_data = pd.DataFrame(bis_rows)
#     obo_data = pd.DataFrame(obo_rows)

#     merged = df.merge(bis_data, how='outer')
#     merged = merged.merge(obo_data, how='outer')
#     return merged


def extract_time(tgz_path, test):

    def lines_that_contain(string, fp):
        for line in fp:
            if string in line:
                return line
        return "empty"

    mylog_path = f'{tmp_dir}/{tgz_path}'

    sp.run(f'mkdir -p {mylog_path}', shell=True)
    sp.run(
        f'tar -xzvf {tgz_path} -C {mylog_path}',
        shell=True,  # stdout=sp.DEVNULL,
        stderr=sp.STDOUT)

    logFilePath = os.path.join(mylog_path, 'sleepy-records/logs/sleepy-script.log')

    with open(logFilePath) as logFile:
        startTime = float(lines_that_contain("FlakeRakeStartTime=", logFile).split("=")[1])

    with open(logFilePath) as logFile:
        stopTime = float(lines_that_contain("FlakeRakeEnd=", logFile).split("=")[1])

    # Remove test scratch work
    shutil.rmtree(mylog_path)
    return stopTime - startTime, startTime


def unpack_sleepylines(df):
    # we can assume every row is a minconfig

    df = df.copy().reset_index()
    df['configIdx'] = df.index

    out = pd.DataFrame(columns=['configIdx', 'Interception'])

    for idx, row in df.iterrows():
        for sline in row.SleepyLines.split(','):
            out = out.append({'configIdx': idx, 'Interception': sline}, ignore_index=True)

    return pd.merge(df, out, how='right')


def work(arg):
    global logs_path

    bis_logs_path = logs_path

    test = arg[0]
    cnt = arg[1]

    print(f'Working {test} as {cnt}', flush=True)

    tgz_path = f'{logs_path}/{test}/sleepy-records.tgz'

    BIS_SKIPPED = f'{BIS}.endedEarly'
    BIS_SKIPPED_MAIN = f'{BIS}.main.skipped'
    OBO_SKIPPED = f'{OBO}.endedEarly'
    OBO_SKIPPED_MAIN = f'{OBO}.main.skipped'

    skip_row = {
        'test': [test],
        BIS_SKIPPED: ['SKIPPED_META_PROCESSING'],
        BIS_SKIPPED_MAIN: ['SKIPPED_META_PROCESSING'],
        OBO_SKIPPED: ['SKIPPED_META_PROCESSING'],
        OBO_SKIPPED_MAIN: ['SKIPPED_META_PROCESSING'],
    }

    # Creating test, sleepyLine.Cause, BIS.min.isPresent, OBO.min.isPresent, thread.encoded

    def _work(path, method):
        global BIS
        global OBO

        # Try to grab time for these tests, not to doing anything with but to fail early if we dont have data.
        try:
            time_spent, flakerake_start_time = extract_time(tgz_path, test)
        except Exception as e:
            print(e)
            print(f'Skipping {test} that does not time')
            return None

        try:
            cause_interception_df = pd.read_csv(f'{path}/report/{report_cause_interception}')
            min_explore_df = pd.read_csv(f'{path}/report/{report_minimal_exploration}')
            min_sleep_df = pd.read_csv(f'{path}/report/{report_minimal_sleep}')
            sha_thread_df = pd.read_csv(f'{path}/report/{report_sha_stacktrace}')

        except FileNotFoundError as e:
            print(e)
            print(f'Skipping {test} that does not have all reports')
            return None

        min_sleep_df = min_sleep_df[['TestMethod', 'Thread', 'Failure']]
        min_sleep_df.drop_duplicates(inplace=True)

        # Before removing minimal from min_explore, merge it min_sleep
        merged = min_sleep_df.merge(min_explore_df)
        # Remove Failures, Minutes because they're not important here

        # Join to get all failure configs, not just the ones that are min.
        # This join is outer, but is effectively right, since exploration table is superset of keys.


        # only nofail
        merged = merged.loc[merged['Failure'] == 'NoFail', :]



        #drop_cols = ['Failure', 'EpochSeconds', 'GlobalExploreID']
        merged.drop_duplicates(inplace=True)

        # Now associate all failConfigs with matched failures
        # We only care about results for this method.
        # Rename columns to make natural join possible

        # Unpack the sleepylines matched with each failure
        merged = unpack_sleepylines(merged)



        # Join the individual sleepylines/interceptions with their causes
        merged = cause_interception_df.merge(merged)
        merged = sha_thread_df.merge(merged)

        # Rename columns
        merged.rename(columns={
            'TestMethod': 'test',
            'StackTrace': 'thread.trace',
            'Thread': 'thread.id',
            'Interception': 'sleepyline',
            'Cause': 'sleepyline.cause',
        }, inplace=True, errors='raise')

        merged = merged[[
            'test',
            'Failure',
            'thread.trace',
            'thread.id',
            'sleepyline.cause',
            'sleepyline',
            'configIdx',
        ]]
        merged.drop_duplicates(inplace=True)
        merged['method'] = method

        return merged

    empty_frame = pd.DataFrame(columns=[
        'test',
        'thread.trace',
        'thread.id',
        'failureMessage',
        'failureID',
        'sleepyline.cause',
        'sleepyline',
        'configIdx',
        'sline.Min',
    ])

    bis_df = _work(f'{bis_logs_path}/{test}', BIS)
    if bis_df is None:
        bis_df = empty_frame.copy()

    # obo_df = _work(f'{obo_logs_path}/{test}', OBO)
    # if obo_df is None:
    #     obo_df = empty_frame.copy()

    output = pd.concat([bis_df])
    output.drop_duplicates(inplace=True)

    skip_df = pd.DataFrame(data=skip_row)

    return [output, skip_df]


def do_it():
    if not use_preprocessed:
        # do this here to avoid replicating work in child procs
        matched_df = None

        tgz_paths = list(map((lambda x: os.path.basename(x)), glob.glob(f'{logs_path}/*')))

        print(f'TotalTests={len(tgz_paths)}', flush=True)

        print(tgz_paths)

        args = (list(zip(tgz_paths, range(len(tgz_paths)), [matched_df] * len(tgz_paths))))

        with mp.Pool() as p:
            all_dfs = p.map(work, args)

            all_dfs = [i[0] for i in all_dfs]

            out_df = pd.concat(all_dfs)
            write_csv(out_df, 'characteristics-no-fails.csv')
    else:
        out_df = pd.read_csv(preprocessed_out_df)
        write_csv(out_df, 'characteristics-no-fails.csv')


if __name__ == '__main__':
    do_it()
