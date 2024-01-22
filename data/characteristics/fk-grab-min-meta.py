import os
import glob

import subprocess as sp
import sys

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

# test_path = '/Users/my/code/flaky-impact/experiments/logback/logback-classic/rerun_vary_time/1642134418.995061'

my_flake_rake = '/Users/my/code/flake-rake'
logs_path = f'{my_flake_rake}/mock-flakerake-logs/final'
scratch = f'{my_flake_rake}/scratch'
matched_failures_slines = f'{my_flake_rake}/matched-failures-all-sleepy-lines.csv'
matched_failures = f'{my_flake_rake}/matched-failures.csv'
output_dir = scratch

if getpass.getuser() == 'flakerake':
    logs_path = '/experiment/flakerake/final-results/detect-results'
    scratch = '/scratch'
    matched_failures_slines = '/experiment/flakerake/final-results/matched-failures-all-sleepy-lines.csv'
    matched_failures = '/experiment/flakerake/final-results/matched-failures.csv'
    output_dir = '/experiment/flakerake/characteristics-5000'

tmp_dir = f'{scratch}/accum-tmp'

use_preprocessed = True

preprocessed_out_df = None
preprocessed_skip_df = None

if use_preprocessed:
    preprocessed_out_df = './characteristics/flakerake-thread-lines-meta-next.csv'
    preprocessed_skip_df = './characteristics/thread-skipped.csv'

MATCHED_DF_SLINES = pd.read_csv(matched_failures_slines)
MATCHED_DF = pd.read_csv(matched_failures)
#MATCHED_DF_SLINES = MATCHED_DF_SLINES.merge(MATCHED_DF)


def write_csv(df, path, index=False):
    print(f'Writing: {path}')
    df.to_csv(path, index=index)


def get_unpacked_matched_failures():
    global matched_failures_slines

    df = MATCHED_DF_SLINES.copy()

    df = df[[  # 'failureID',
        'test',
        'failureMessage',
        'failureID',
        'FailConfigs.flakerake',
        'FailConfigs.flakerake-obo',
    ]]
    df = df.reset_index()
    df['matchedIdx'] = df.index

    out = pd.DataFrame(columns=[
        'matchedIdx',
        'Thread.BIS',
        'SleepyLines.BIS',
        'Thread.OBO',
        'SleepyLines.OBO',
    ])

    bis_rows = []
    obo_rows = []
    for idx, row in df.iterrows():
        print(f'Did {idx}/{len(df)}')
        has_flakerake_config = False

        out_row = None

        if not pd.isna(row['FailConfigs.flakerake']):
            has_flakerake_config = True
            for config in row['FailConfigs.flakerake'].split(';'):
                out_row = {
                    'matchedIdx': idx,
                }
                thread = config.split(' ')[0]
                slines = config.split(' ')[1]
                out_row['Thread.BIS'] = thread
                out_row['SleepyLines.BIS'] = slines
                bis_rows.append(out_row)

        if not pd.isna(row['FailConfigs.flakerake-obo']):
            has_flakerake_config = True
            for config in row['FailConfigs.flakerake-obo'].split(';'):
                out_row = {
                    'matchedIdx': idx,
                }
                thread = config.split(' ')[0]
                slines = config.split(' ')[1]
                out_row['Thread.OBO'] = thread
                out_row['SleepyLines.OBO'] = slines
                obo_rows.append(out_row)

        if has_flakerake_config:
            out = out.append(out_row, ignore_index=True)

    bis_data = pd.DataFrame(bis_rows)
    obo_data = pd.DataFrame(obo_rows)

    merged = df.merge(bis_data, how='outer')
    merged = merged.merge(obo_data, how='outer')
    return merged


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
    obo_logs_path = f'{logs_path}-obo'

    test = arg[0]
    cnt = arg[1]
    matched_df = arg[2]

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

        min_sleep_df = min_sleep_df[['TestMethod', 'Thread', 'SleepyLines']]

        # Drop NoFails and already fails stably
        min_sleep_df = min_sleep_df[min_sleep_df['SleepyLines'] != 'NoFail']
        min_sleep_df = min_sleep_df[min_sleep_df['SleepyLines'] != 'AlreadyFailsStably']
        min_sleep_df = min_sleep_df[min_sleep_df['SleepyLines'] != 'TestMethodAnalysisExceeded 24.0 Hours']

        min_explore_df = min_explore_df[min_explore_df['SleepyLines'] != 'NoFail']
        min_explore_df = min_explore_df[min_explore_df['SleepyLines'] != 'AlreadyFailsStably']
        min_explore_df = min_explore_df[min_explore_df['SleepyLines'] != 'TestMethodAnalysisExceeded 24.0 Hours']

        min_sleep_df.drop_duplicates(inplace=True)

        SKIPPED = f'{method}.endedEarly'
        SKIPPED_MAIN = f'{method}.main.skipped'

        skip_row[SKIPPED] = (len(min_sleep_df.loc[min_sleep_df['SleepyLines'] == ENDED_EARLY, 'Thread'])) > 0
        skip_row[SKIPPED_MAIN] = (len(min_sleep_df.loc[min_sleep_df['Thread'] == MAIN, 'Thread'])) < 1

        # Before removing minimal from min_explore, merge it min_sleep
        merged = min_sleep_df.merge(min_explore_df)

        if len(merged) <= 0:
            print(f'Skipping {test} with no failures found')

            if len(min_sleep_df) > 0:
                min_sleep_df.to_csv('wtf.csv')
                min_explore_df.to_csv('wtf2.csv')
                raise ValueError

            return None

        # Remove anything that isnt maximal from min_explore
        # All maximal data
        min_explore_df = min_explore_df.sort_values('GlobalExploreID').drop_duplicates(subset=['TestMethod', 'Thread'], keep="first")

        # Remove Failures, Minutes because they're not important here

        # Join to get all failure configs, not just the ones that are min.
        # This join is outer, but is effectively right, since exploration table is superset of keys.
        merged = merged.merge(
            min_explore_df,
            how='outer',
            indicator=True,
        )

        # Drop all NoFail
        merged = merged.loc[merged['Failure'] != 'NoFail', :]

        # Configs that are both are min since these rows were provided by the minimal
        merged['_merge'].replace(to_replace='both', value=True, inplace=True)
        merged['_merge'].replace(to_replace='left_only', value=True, inplace=True)
        merged['_merge'].replace(to_replace='right_only', value=False, inplace=True)
        merged.rename(columns={'_merge': 'sline.Min'}, inplace=True)

        # Describe as anything that is NoFail as maximal and sline.Min as False
        merged.loc[merged['Failure'] == 'NoFail', 'sline.Min'] = False

        #drop_cols = ['Failure', 'EpochSeconds', 'GlobalExploreID']
        drop_cols = [
            'Failure',
        ]
        merged.drop(columns=drop_cols, inplace=True)
        merged.drop_duplicates(inplace=True)

        # Now associate all failConfigs with matched failures
        matched_method_df = matched_df.copy()
        # We only care about results for this method.
        matched_method_df = matched_method_df[[
            'test',
            'failureMessage',
            'failureID',
            f'SleepyLines.{method}',
            f'Thread.{method}',
        ]]
        # Rename columns to make natural join possible
        matched_method_df.rename(columns={
            'test': 'TestMethod',
            f'Thread.{method}': 'Thread',
            f'SleepyLines.{method}': 'SleepyLines',
        }, inplace=True, errors='raise')

        # Now merged includes columns from matched-failures
        # Left because we want to keep our maximumal configs
        merged = merged.merge(matched_method_df, how='left', indicator=True)
        merged = merged.drop_duplicates()

        merged.loc[merged['sline.Min'] == False, 'failureID'] = "MAXIMAL_CONFIG"
        merged.loc[merged['sline.Min'] == False, 'failureMessage'] = "MAXIMAL_CONFIG"

        merged['failureID'].fillna("MIN_BUT_MISSING_FROM_MATCHED", inplace=True)
        merged['failureMessage'].fillna("MIN_BUT_MISSING_FROM_MATCHED", inplace=True)

        # merged.loc[(merged['sline.Min'] == 'True') & (merged['failureID'] == 'MAXIMAL_CONFIG'), 'failureID'] = "MIN_BUT_MISSING_FROM_MATCHED"

        # merged.loc[merged['sline.Min'] == 'True', 'failureMessage'] = "MIN_BUT_MISSING_FROM_MATCHED"

        # merged.loc[merged['failureID'] == 'MAXIMAL_CONFIG',
        #            ['failureID', 'failureMessage']] = "MIN_BUT_MISSING_FROM_MATCHED"

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
            'thread.trace',
            'thread.id',
            'failureMessage',
            'failureID',
            'GlobalExploreID',
            'EpochSeconds',
            'sleepyline.cause',
            'sleepyline',
            'configIdx',
            'sline.Min',
        ]]
        merged.drop_duplicates(inplace=True)
        merged['method'] = method

        # No we do the extra work for sleep
        def combine_slines_as_sorted__interception_df(df):
            df = df.copy().reset_index().rename(columns={'TestMethod': 'test', 'Thread': 'thread.id', 'Interception': 'sleepyline'})
            df_needed = df[['test', 'thread.id', 'SleepyRunId', 'sleepyline']]
            df_group = df_needed.sort_values(by=['test', 'thread.id', 'SleepyRunId', 'sleepyline'])\
                                .drop_duplicates(subset=['test', 'thread.id', 'SleepyRunId', 'sleepyline'])\
                                .groupby(['test', 'thread.id', 'SleepyRunId'])
            df_agg = df_group.agg({'sleepyline': ' '.join}).reset_index()
            df_agg = df_agg.rename(columns={'sleepyline': 'slines.sort'}).reset_index(drop=True, ).drop(columns=['index'], errors='ignore')
            return df.merge(df_agg)

        def combine_slines_as_sorted__merged_df(df):
            # Append slines.sorted column to argument df
            df = df.copy().reset_index()
            df_needed = df[['test', 'thread.id', 'configIdx', 'sleepyline']]
            df_group = df_needed.sort_values(by=['test', 'thread.id', 'configIdx', 'sleepyline'])\
                                .drop_duplicates(subset=['test', 'thread.id', 'configIdx', 'sleepyline'])\
                                .groupby(['test', 'thread.id', 'configIdx'])
            df_agg = df_group.agg({'sleepyline': ' '.join}).reset_index()
            df_agg = df_agg.rename(columns={'sleepyline': 'slines.sort'}).reset_index(drop=True, ).drop(columns=['index'], errors='ignore')
            return df.merge(df_agg)

        #interception_w_sorted = combine_slines_as_sorted__interception_df(cause_interception_df).drop(columns=['index'], errors='ignore')
        #merged_w_sorted = combine_slines_as_sorted__merged_df(merged).drop(columns=['index'], errors='ignore')
        #final_merged = merged_w_sorted.merge(interception_w_sorted)

        #return final_merged
        merged['flakerake.startTime'] = flakerake_start_time
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
    empty_frame = empty_frame.append(
        {
            'test': test,
            'thread.trace': 'MISSING',
            'thread.id': 'MISSING',
            'failureMessage': 'MISSING',
            'failureID': 'MISSING',
            'sleepyline.cause': 'MISSING',
            'sleepyline': 'MISSING',
            'configIdx': 'MISSING',
            'sline.Min': 'MISSING',
        },
        ignore_index=True)

    bis_df = _work(f'{bis_logs_path}/{test}', BIS)
    if bis_df is None:
        bis_df = empty_frame.copy()

    obo_df = _work(f'{obo_logs_path}/{test}', OBO)
    if obo_df is None:
        obo_df = empty_frame.copy()

    output = pd.concat([bis_df, obo_df])
    output.drop_duplicates(inplace=True)

    skip_df = pd.DataFrame(data=skip_row)

    return [output, skip_df]


def do_all():

    if not use_preprocessed:
        # do this here to avoid replicating work in child procs
        matched_df = get_unpacked_matched_failures()

        tgz_paths = list(map((lambda x: os.path.basename(x)), glob.glob(f'{logs_path}/*')))

        print(f'TotalTests={len(tgz_paths)}', flush=True)

        print(tgz_paths)

        args = (list(zip(tgz_paths, range(len(tgz_paths)), [matched_df] * len(tgz_paths))))

        with mp.Pool() as p:
            all_dfs = p.map(work, args)

            skip_dfs = [i[1] for i in all_dfs]
            all_dfs = [i[0] for i in all_dfs]

            out_df = pd.concat(all_dfs)
            skip_df = pd.concat(skip_dfs)
    else:
        out_df = pd.read_csv(preprocessed_out_df)
        skip_df = pd.read_csv(preprocessed_skip_df)

    # Write flagged_api csv
    if use_preprocessed:
        flagged_api_to_line = pd.read_csv('./characteristics/flaggedAPI-to-sline.csv')
    else:
        flagged_api_to_line = out_df.copy().loc[~out_df['sleepyline.cause'].isin(abstract_sline_causes), ['sleepyline.cause', 'sleepyline']]
        flagged_api_to_line.rename(columns={'sleepyline.cause': 'flaggedAPI'})
        flagged_api_to_line.drop_duplicates(inplace=True)

    # Write total csv
    # We want to merged only with matched
    matched_only_tests = MATCHED_DF.loc[(MATCHED_DF['flakerake'] >= 1) | (MATCHED_DF['flakerake-obo'] >= 1), ['test']].drop_duplicates()
    out_df = out_df.merge(matched_only_tests)

    out_df.loc[~out_df['sleepyline.cause'].isin(abstract_sline_causes), 'sleepyline.cause'] = "FLAGGED_API"
    out_df.drop_duplicates(inplace=True)
    write_csv(out_df, f'{output_dir}/flakerake-thread-lines-meta-next.csv', index=False)

    # Get pipe in thread csv for coauthor
    pipe_replaced_comma_filename = 'flakerake-thread-lines-meta-next-pipe-in-tid.csv'
    sed_cmd = r"sed -e 's/,\([0-9][0-9]*\)>/|\1>/'"
    if use_preprocessed:
        os.system(f"cat characteristics-5000/flakerake-thread-lines-meta-next.csv | {sed_cmd} > {output_dir}/{pipe_replaced_comma_filename}")
    else:
        os.system(f"cat {output_dir}/flakerake-thread-lines-meta-next.csv | {sed_cmd} > {output_dir}/{pipe_replaced_comma_filename}")

    pipe_in_tid_df = pd.read_csv(f'{output_dir}/{pipe_replaced_comma_filename}')

    # Remove banned flakerake-specific failures
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureMessage'] != ('SleepyTimeOut(ProbableDeadlock)')]
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureMessage'] != ('MISSING')]
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureMessage'] != ('MIN_BUT_MISSING_FROM_MATCHED')]

    MAXIMAL_CONFIG = 'MAXIMAL_CONFIG'

    def _validate():
        # Validate maxial config tests are 1..1 with matched_df
        df_maximal_only = pipe_in_tid_df.loc[pipe_in_tid_df['failureID'] == MAXIMAL_CONFIG, [
            'test',
        ]].drop_duplicates()
        df_maximal_only.merge(MATCHED_DF_SLINES[[
            'test',
        ]].drop_duplicates(), validate='1:1')
        print('Validated Maximal Configs with Matched')

        # Validate minimal configs are 1..1 with matched
        df_minimal_only = pipe_in_tid_df.loc[pipe_in_tid_df['failureID'] != MAXIMAL_CONFIG, ['test', 'failureID']].drop_duplicates()
        df_minimal_only.merge(MATCHED_DF_SLINES[['test', 'failureID']].drop_duplicates(), validate='1:1')
        print('Validated Minimal Configs with Matched')

    _validate()

    # Create threads csv
    pipe_in_tid_threads_df = pipe_in_tid_df.copy()[['thread.trace', 'thread.id']]
    pipe_in_tid_threads_df.drop_duplicates(inplace=True)
    write_csv(pipe_in_tid_threads_df, f'{tmp_dir}/flakerake-thread-lines-meta-next-pipe-in-tid_threads.csv', index=False)

    # Create original csv with pipes, but without the trace.trace
    pipe_in_tid_no_thread_trace_df = pipe_in_tid_df.drop(columns=['thread.trace'])
    write_csv(pipe_in_tid_no_thread_trace_df, f'{tmp_dir}/flakerake-thread-lines-meta-next-pipe-in-tid_no-thread-trace.csv', index=False)

    characteristic_data_path = './scratch'

    # Deploy to jbvm if running on flakerake machine
    if getpass.getuser() == 'flakerake':
        characteristic_data_path = '/experiment/flakerake/characteristics'

    # Move original over
    os.system(f'mv {tmp_dir}/flakerake-thread-lines-meta-next.csv {characteristic_data_path}/flakerake-thread-lines-meta-next.csv')
    # Move pipe replaced thread csv over
    os.system(f'mv {tmp_dir}/flakerake-thread-lines-meta-next-pipe-in-tid_no-thread-trace.csv {characteristic_data_path}/flakerake-thread-lines-meta-next-pipe-in-tid_no-thread-trace.csv')
    # Move pipe replaced original without trace over
    os.system(f'mv {tmp_dir}/flakerake-thread-lines-meta-next-pipe-in-tid_threads.csv {characteristic_data_path}/flakerake-thread-lines-meta-next-pipe-in-tid_threads.csv')
    # Write out the flagged api
    write_csv(flagged_api_to_line, f'{characteristic_data_path}/flaggedAPI-to-sline.csv', index=False)

    # Write what was skipped
    write_csv(skip_df, f'{characteristic_data_path}/thread-skipped.csv', index=False)

    # Type issues below?
    # For CSV `test,failureID,min.sleepyline.size`:
    # Groupby test,failireID,configIdx and aggregrate rows
    def slineMin_size():
        slineMin_size = pipe_in_tid_df.copy().loc[(pipe_in_tid_df['sline.Min'] == True) | (pipe_in_tid_df['sline.Min'] == 'True'), :].groupby(['test', 'failureID', 'configIdx',
                                                                                                                                               'method']).size().reset_index(name='sline.size')
        # THIS WAS WRONG slineMin_size = pipe_in_tid_df[pipe_in_tid_df['sline.Min'] == 'True'].groupby(['test', 'failureID', 'configIdx', 'method']).size().reindex()
        write_csv(slineMin_size, f'{characteristic_data_path}/sline.Min-size.csv', index=False)

    def slineMax_size():
        # THIS WAS WRONG slineMax_size = pipe_in_tid_df[pipe_in_tid_df['sline.Min'] == 'False'].groupby(['test', 'failureID', 'configIdx', 'method']).size().reset_index(name='sline.size')
        slineMax_size = pipe_in_tid_df.copy()[(pipe_in_tid_df['sline.Min'] == 'False') | (pipe_in_tid_df['sline.Min'] == False)].groupby(['test', 'failureID', 'configIdx',
                                                                                                                                          'method']).size().reset_index(name='sline.size')
        write_csv(slineMax_size, f'{characteristic_data_path}/sline.Max-size.csv', index=False)

    def slineMaxUnion_with_size():
        out_maximal = out_df[['test', 'method', 'sleepyline']]
        out_maximal = out_maximal.drop_duplicates()
        out_max_cnt = out_maximal.groupby(['test', 'method']).count()
        write_csv(out_max_cnt, f'{characteristic_data_path}/sline.Max.Union.By-Method-size.csv', index=False)

        out_all_max = out_df[['test', 'sleepyline']]
        out_all_max = out_all_max.drop_duplicates()
        out_all_max_cnt = out_all_max.groupby('test').count()
        write_csv(out_all_max_cnt, f'{characteristic_data_path}/sline.Max.Union-size.csv', index=False)

    # From here on out, only use what's in matched
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureID'] != 'MIN_BUT_MISSING_FROM_MATCHED', :]
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['sleepyline'] != 'MISSING', :]
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureID'] != 'SleepyTimeOut(ProbableDeadlock)', :]
    pipe_in_tid_df_max = pipe_in_tid_df.copy()
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureID'] != 'MAXIMAL_CONFIG', :]

    # Regrab line level detail of causes
    causeToConfigNonFlaggedAPI = pipe_in_tid_df.copy().loc[pipe_in_tid_df['sleepyline.cause'] != 'FLAGGED_API', ['method', 'test', 'configIdx', 'sleepyline', 'sleepyline.cause', 'failureID']]
    causeToConfigFlaggedAPI = pipe_in_tid_df.copy().loc[pipe_in_tid_df['sleepyline.cause'] == 'FLAGGED_API', ['method', 'test', 'configIdx', 'sleepyline', 'failureID']]
    # Merge with flagged api causes
    causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.merge(flagged_api_to_line)
    causeToConfigFlaggedAPI = pd.concat([causeToConfigFlaggedAPI, causeToConfigNonFlaggedAPI])
    causeToConfigFlaggedAPIConst = causeToConfigFlaggedAPI.copy()

    # MAX BEGIN
    causeToConfigMaxNonFlaggedAPI = pipe_in_tid_df_max.copy().loc[pipe_in_tid_df_max['sleepyline.cause'] != 'FLAGGED_API',
                                                                  ['method', 'test', 'configIdx', 'sleepyline', 'sleepyline.cause', 'failureID']]
    causeToConfigMaxFlaggedAPI = pipe_in_tid_df_max.copy().loc[pipe_in_tid_df_max['sleepyline.cause'] == 'FLAGGED_API', ['method', 'test', 'configIdx', 'sleepyline', 'failureID']]
    # Merge with flagged api causes
    causeToConfigMaxFlaggedAPI = causeToConfigMaxFlaggedAPI.merge(flagged_api_to_line)
    causeToConfigMaxFlaggedAPI = pd.concat([causeToConfigMaxFlaggedAPI, causeToConfigMaxNonFlaggedAPI])
    causeToConfigMaxFlaggedAPIConst = causeToConfigMaxFlaggedAPI.copy()
    # MAX END

    flagged_api_causes = flagged_api_to_line.copy().loc[flagged_api_to_line['sleepyline.cause'] != 'MISSING', 'sleepyline.cause'].drop_duplicates().sort_values()

    all_causes = abstract_sline_causes + list(flagged_api_causes)

    # Sleep point & Total unique failures that this sleep point is used in the minimal set of sleeps [This is number of failures
    def slineCauseToUniqFailure_count():
        #FAILURES ARE failureID test pairs
        slineCauseToUniqFailure_count = causeToConfigFlaggedAPI.copy().loc[:, ['failureID', 'sleepyline.cause', 'method', 'test']].drop_duplicates()
        slineCauseToUniqFailure_count = slineCauseToUniqFailure_count.groupby(['sleepyline.cause', 'method']).count().reset_index().rename(columns={'failureID': 'failureID.Uniq.Count'})
        write_csv(slineCauseToUniqFailure_count, f'{characteristic_data_path}/slineCause.ToUniqFailure-count.csv', index=False)

    ### SLINES ####

    # Total unique tests used in the minimal set of sleeps [This is number of tests]
    # minSleep method, configIdx, sline and sort and combine the slines
    # minSetToUniqTests = pipe_in_tid_df.copy().loc[:, ['sleepyline', 'method', 'configIdx', 'test']].drop_duplicates()
    # Add count to it because we probably want that.
    # minSetToUniqTestsCount = minSetToUniqTests.copy().groupby(['method', 'test', 'configIdx']).count().reset_index().rename(columns={'sleepyline':'sline.count'})

    # minSetToUniqTests = minSetToUniqTests.sort_values(by='sleepyline').groupby(['method', 'configIdx', 'test', ]).agg({'sleepyline': ' '.join}).reset_index()
    # minSetToUniqTests = minSetToUniqTests.merge(minSetToUniqTestsCount)

    # minSetToUniqTests = minSetToUniqTests[['method','test','sleepyline', 'sline.count']].drop_duplicates().groupby(['method', 'sleepyline', 'sline.count']).count().reset_index()
    # minSetToUniqTests = minSetToUniqTests.rename(columns={'test': 'test.uniq-count', 'sleepyline': 'minSlines.sorted'})
    # minSetToUniqTests.to_csv(f'{characteristic_data_path}/minSlinesToTest-Count.csv', index=False)

    pipe_in_tid_df.to_csv('test-meta.csv')

    #Just get rid of obo
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['method'] == 'BIS']

    ### CAUSES ###

    # Total unique tests used in the minimal set of sleeps [This is number of tests]
    # minSleep method, configIdx, sline and sort and combine the slines
    def minSetToUniqTests():
        minSetToUniqTests = pipe_in_tid_df.copy().loc[:, ['sleepyline.cause', 'method', 'configIdx', 'test']].drop_duplicates()
        # Add count to it because we probably want that.
        minSetToUniqTestsCount = minSetToUniqTests.copy().groupby(['method', 'test', 'configIdx']).count().reset_index().rename(columns={'sleepyline.cause': 'cause.count'})

        minSetToUniqTests = minSetToUniqTests.sort_values(by='sleepyline.cause').groupby([
            'method',
            'configIdx',
            'test',
        ]).agg({
            'sleepyline.cause': ' '.join
        }).reset_index()
        minSetToUniqTests = minSetToUniqTests.merge(minSetToUniqTestsCount)

        minSetToUniqTests = minSetToUniqTests[['method', 'test', 'sleepyline.cause', 'cause.count']].drop_duplicates().groupby(['method', 'sleepyline.cause', 'cause.count']).count().reset_index()
        minSetToUniqTests = minSetToUniqTests.rename(columns={'test': 'test.uniq-count', 'sleepyline.cause': 'minCauses.sorted'})
        write_csv(minSetToUniqTests, f'{characteristic_data_path}/minCausesToTest-Count.csv', index=False)

    def do_correlations():
        # Gets us the correlations wrt to failureIDs of various configs

        # # Most common co-occurring sleep points
        # # Compute correlation matrix
        # # NOT UNIQ
        # causeToConfig = pipe_in_tid_df.copy()[['method', 'configIdx', 'sleepyline.cause', 'failureID']]

        # # Set them to zero
        # for cause in abstract_sline_causes:
        #     causeToConfig[cause] = 0

        # # Set them that match to 1
        # for cause in abstract_sline_causes:
        #     causeToConfig.loc[causeToConfig['sleepyline.cause'] == cause, cause] = 1

        # Commenting out the non all causes correlation matrix
        # # DO NOT MAKE THEM UNIQ
        # causeToConfig = causeToConfig.drop(columns=['sleepyline.cause'])
        # causeToConfig = causeToConfig.groupby(['method', 'failureID', 'configIdx', ]).sum().reset_index().drop(columns=['configIdx'])

        # causeToConfigBIS = causeToConfig.loc[causeToConfig['method'] == BIS, abstract_sline_causes]
        # causeToConfigBISCorr = causeToConfigBIS.corr()
        # causeToConfigBISCorr.to_csv(f'{characteristic_data_path}/bis_corr.csv')

        # causeToConfigOBO = causeToConfig.loc[causeToConfig['method'] == OBO, abstract_sline_causes]
        # causeToConfigOBOCorr = causeToConfigOBO.corr()
        # causeToConfigOBOCorr.to_csv(f'{characteristic_data_path}/obo_corr.csv')

        # # ALL CAUSES

        # # Most common co-occurring sleep points thare are FLAGGED API
        # # Compute correlation matrix
        # # NOT UNIQ
        # causeToConfigFlaggedAPI = pipe_in_tid_df.copy()[['method', 'failureID', 'configIdx', 'sleepyline.cause', 'sleepyline']].drop_duplicates()
        # # Only care about flagged api ones here
        # # pdb.set_trace()
        # causeToConfigNonFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] != 'FLAGGED_API', ['method', 'failureID', 'configIdx', 'sleepyline']]
        # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] == 'FLAGGED_API', ['method', 'failureID', 'configIdx', 'sleepyline']]
        # # Merge with flagged api causes
        # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.merge(flagged_api_to_line)
        # causeToConfigFlaggedAPI = pd.concat([causeToConfigFlaggedAPI, causeToConfigNonFlaggedAPI])

        # # Set them to zero
        # for cause in all_causes:
        #     causeToConfigFlaggedAPI[cause] = 0

        # # Set them that match to 1
        # for cause in all_causes:
        #     causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] == cause, cause] = 1

        # # THESE ARE BY CONFIG AND TEST DO NOT MAKE THEM UNIQ, we want configs for each test
        # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.drop(columns=['sleepyline.cause'])
        # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.groupby(['method', 'failureID', 'configIdx', ]).sum().reset_index().drop(columns=['configIdx'])

        # causeToConfigFlaggedAPIBIS = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['method'] == BIS, all_causes]

        # # Sometimes we only have one config with a particular cause for a given test
        # causeToConfigFlaggedAPIBISCorr = causeToConfigFlaggedAPIBIS.corr().fillna(value=0)
        # causeToConfigFlaggedAPIBISCorr.to_csv(f'{characteristic_data_path}/bis_all-cause_corr.csv')

        # causeToConfigFlaggedAPIOBO = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['method'] == OBO, all_causes]

        # # Sometimes we only have one config with a particular cause for a given test
        # causeToConfigFlaggedAPIOBOCorr = causeToConfigFlaggedAPIOBO.corr().fillna(value=0)
        # causeToConfigFlaggedAPIOBOCorr.to_csv(f'{characteristic_data_path}/obo_all-cause_corr.csv')

        all_causes = abstract_sline_causes + list(flagged_api_causes)

        # Now do the above for only size 1 leaves
        # NOT UNIQ
        causeToConfigFlaggedAPI = pipe_in_tid_df.copy()[['method', 'test', 'failureID', 'configIdx', 'sleepyline.cause', 'sleepyline']].drop_duplicates()

        # Get only size 1 leaf nodes
        min_sizes = pd.read_csv('./scratch/sline.Min-size.csv')
        causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.merge(min_sizes)
        causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sline.size'] == 1, :]

        # Separate into those that must be merged with sline causes to get the original cause and those that do not.
        causeToConfigNonFlaggedAPI = causeToConfigFlaggedAPI.copy().loc[causeToConfigFlaggedAPI['sleepyline.cause'] != 'FLAGGED_API',
                                                                        ['method', 'failureID', 'configIdx', 'sleepyline', 'sleepyline.cause']]

        causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.copy().loc[causeToConfigFlaggedAPI['sleepyline.cause'] == 'FLAGGED_API', ['method', 'failureID', 'configIdx', 'sleepyline']]

        # Get the original causes to begin with
        causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.merge(flagged_api_to_line)
        causeToConfigFlaggedAPI = pd.concat([causeToConfigFlaggedAPI, causeToConfigNonFlaggedAPI])

        # Get all causes and remove the abstract cause FLAGGED_API
        all_causes = abstract_sline_causes[1:] + list(flagged_api_causes)

        if 'FLAGGED_API' in all_causes:
            print('found flagged api when it shouldnt')

        # Set them to zero
        for cause in all_causes:
            causeToConfigFlaggedAPI[cause] = 0

        # Set them that match to 1
        for cause in all_causes:
            causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] == cause, cause] = 1
            #causeToConfigFlaggedAPI[cause] = causeToConfigFlaggedAPI['sleepyline.cause'].apply(lambda x: 1)

        # Only doing BIS
        causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['method'] == BIS, :]

        causeToConfigFlaggedAPI.to_csv('corr-test.csv')

        # THESE ARE BY CONFIG AND TEST DO NOT MAKE THEM UNIQ, we want configs for each test
        causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.drop(columns=['sleepyline.cause', 'configIdx', 'method'])
        causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.groupby([
            'failureID',
        ]).sum().reset_index()

        causeToConfigFlaggedAPI.to_csv('corr-test2.csv')

        # causeToConfigFlaggedAPIBIS = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['method'] == BIS, all_causes]

        # # Sometimes we only have one config with a particular cause for a given failure
        # causeToConfigFlaggedAPIBISCorr = causeToConfigFlaggedAPIBIS.corr().fillna(value=0)
        # causeToConfigFlaggedAPIBISCorr.to_csv(f'{characteristic_data_path}/bis_all-size-1-leaves-cause_corr.csv')

        #causeToConfigFlaggedAPIBIS = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['method'] == BIS, all_causes]

        # Sometimes we only have one config with a particular cause for a given failure
        causeToConfigFlaggedAPIBISCorr = causeToConfigFlaggedAPI.corr().fillna(value=0)
        write_csv(causeToConfigFlaggedAPIBISCorr, f'{characteristic_data_path}/bis_all-size-1-leaves-cause_corr.csv', index=True)

    def cause_proportion_per_project():
        # When you do find a leaf node, how often is it that this sleepy cause is related to the leaf node
        matched_df_original = pd.read_csv(matched_failures_slines)
        causeToConfig = pipe_in_tid_df.copy().merge(matched_df_original[['slug', 'test']])
        causeToConfig = causeToConfig[['slug', 'method', 'test', 'configIdx', 'sleepyline.cause']]
        causeToConfig = causeToConfigFlaggedAPIConst.copy()

        # Set them to zero
        for cause in all_causes:
            causeToConfig[cause] = 0

        # Set them that match to 1
        for cause in all_causes:
            causeToConfig.loc[causeToConfig['sleepyline.cause'] == cause, cause] = 1

        # THESE ARE BY CONFIG AND TEST DO NOT MAKE THEM UNIQ
        causeToConfigByProject = causeToConfig.copy().groupby([
            'method',
            'slug',
        ]).mean().reset_index()
        write_csv(causeToConfigByProject, f'{characteristic_data_path}/proportion_of_causes_in_leaf_per_project-method.csv', index=False)

    def cause_proportion_count_all_projects():
        # Get unique tests per cause
        cause_method_to_test = causeToConfigFlaggedAPIConst.copy()[['sleepyline.cause', 'method', 'test']].drop_duplicates()
        cause_method_to_test = cause_method_to_test.groupby(['sleepyline.cause', 'method']).count().reset_index()
        cause_method_to_test.rename(columns={'test': 'test.count'}, inplace=True)
        write_csv(cause_method_to_test, f'{characteristic_data_path}/cause_method_to_test_count.csv', index=False)

        # THESE ARE BY CONFIG AND TEST DO NOT MAKE THEM UNIQ
        causeToConfig = causeToConfigFlaggedAPIConst.copy()[['sleepyline.cause', 'method', 'configIdx', 'test']].drop_duplicates()
        # causeToConfig = causeToConfig.drop(columns=['sleepyline.cause', 'configIdx'])

        causeToConfigCount = causeToConfig.copy().groupby([
            'method',
            'sleepyline.cause',
        ]).count().reset_index()
        write_csv(causeToConfigCount, f'{characteristic_data_path}/count_of_causes_in_leaf_all_projects-method.csv', index=False)

        config_count = pipe_in_tid_df.copy()[['method', 'test', 'configIdx']].drop_duplicates().groupby('method').count().reset_index()[['method', 'configIdx']]
        config_count.rename(columns={'configIdx': 'totalConfigs'}, inplace=True)
        print(config_count)

        causeToConfigProp = config_count.merge(causeToConfigCount)
        causeToConfigProp['proportion'] = causeToConfigProp['configIdx'] / causeToConfigProp['totalConfigs']
        causeToConfigProp = causeToConfigProp.drop(columns=['test']).rename(columns={'configIdx': 'config.Count'})
        write_csv(causeToConfigProp, f'{characteristic_data_path}/proportion_of_causes_in_leaf_all_projects-method.csv', index=False)

    def get_only_maximal():
        df = causeToConfigMaxFlaggedAPIConst.copy()
        df = df.loc[df['failureID'] == MAXIMAL_CONFIG]
        maximal_causes_count = df[['sleepyline.cause']].drop_duplicates().count()
        print(f'max causes count={maximal_causes_count}')
        write_csv(df, 'maximal.csv')

    def get_only_min():
        df = causeToConfigFlaggedAPIConst.copy()
        df = df.loc[df['failureID'] != MAXIMAL_CONFIG]
        min_causes_count = df[['sleepyline.cause']].drop_duplicates().count()
        print(f'min causes count={min_causes_count}')
        write_csv(df, 'min.csv')

    def get_all_intercepted_causes():
        path = 'characteristics-no-fails.csv'
        no_fails = pd.read_csv(path)
        df = causeToConfigFlaggedAPIConst.copy()

        # Get all causes
        no_fail_cause = no_fails[['sleepyline.cause']].drop_duplicates()
        df_cause = df[['sleepyline.cause']].drop_duplicates()

        merged = no_fail_cause.merge(df_cause, how='outer').drop_duplicates()
        df_cause_count = merged.count()
        print(f'all causes count={df_cause_count}')
        write_csv(df_cause_count, 'all-causes.csv')

    # Uncomment these to do the specific analysis
    minSetToUniqTests()
    slineMin_size()
    do_correlations()
    slineCauseToUniqFailure_count()
    cause_proportion_count_all_projects()
    slineMax_size()
    get_only_maximal()
    get_only_min()
    get_all_intercepted_causes()


def write_latex_tables():

    # characteristics = './characteristics'

    pipe_replaced_comma_filename = 'flakerake-thread-lines-meta-next-pipe-in-tid.csv'
    pipe_in_tid_df = pd.read_csv(f'{output_dir}/{pipe_replaced_comma_filename}')
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureMessage'] != ('SleepyTimeOut(ProbableDeadlock)')]
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureMessage'] != ('MISSING')]
    pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureMessage'] != ('MIN_BUT_MISSING_FROM_MATCHED')]

    bis_corr = pd.read_csv('./scratch/bis_all-size-1-leaves-cause_corr.csv', index_col=0)

    # print('begin latex!!')
    # print(causeToConfigOBOCorr.to_latex(escape=False))
    # print('end latex!!')

    def report_most_bis_correlated(df):
        pairs = set()
        df = df.copy().unstack().sort_values(ascending=False)
        # Get rid of self correlation
        keep_rows = [x[0] != x[1] for x in df.index]
        report = df.loc[keep_rows, :]
        # Now get rid of commutative duplicate pairs
        keep_rows = []
        for row in report.index:
            row_commuted = tuple([row[1], row[0]])
            if row in pairs:
                keep_rows.append(False)
            elif row_commuted in pairs:
                keep_rows.append(False)
            else:
                pairs.add(row)
                keep_rows.append(True)

        report = report.loc[keep_rows, :].reset_index()
        report = report.rename(columns={0: 'Correlation', 'level_0': 'API', 'level_1': 'API'})
        report_bottom = report.nsmallest(5, 'Correlation')
        report_top = report.nlargest(20, 'Correlation')

        write_csv(report_top, 'top_5_bis_corr.csv', index=False)
        write_csv(report_bottom, 'bottom_5_bis_corr.csv', index=False)

        report = report.loc[report['Correlation'] != 1.0, :]
        write_csv(report, 'top_bis_corr_no_1.csv', index=False)
        report_bottom = report.nsmallest(100, 'Correlation')

        return report_top

    # Get the characteristics table, do merges and write as latex
    cause_count_prop = pd.read_csv('./scratch/proportion_of_causes_in_leaf_all_projects-method.csv')
    cause_to_uniq_failure = pd.read_csv('./scratch/slineCause.ToUniqFailure-count.csv')
    cause_to_uniq_test = pd.read_csv('./scratch/cause_method_to_test_count.csv')

    merged = pd.merge(cause_count_prop, cause_to_uniq_failure)
    merged = merged.merge(cause_to_uniq_test).drop(columns=['totalConfigs'])
    merged = merged.loc[merged['method'] == 'BIS', :].sort_values(by='test.count', ascending=False)
    n = 10
    topn_causes = merged.iloc[0:n].copy().drop(columns='method')

    topn_causes.to_csv('test.csv')

    # pipe_in_tid_df = pd.read_csv('./scratch/flakerake-thread-lines-meta-next-pipe-in-tid_no-thread-trace.csv')
    # # From here on out, only use what's in matched
    # pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureID'] != 'MAXIMAL_CONFIG', :]
    # pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['failureID'] != 'MIN_BUT_MISSING_FROM_MATCHED', :]
    # pipe_in_tid_df = pipe_in_tid_df.loc[pipe_in_tid_df['sleepyline'] != 'MISSING', :]
    # pipe_in_tid_df_obo = pipe_in_tid_df.loc[pipe_in_tid_df['method'] == 'OBO', :]

    # # Get all causes
    # flagged_api_to_line = pd.read_csv('./scratch/flaggedAPI-to-sline.csv')
    # flagged_api_causes = flagged_api_to_line.copy().loc[flagged_api_to_line['sleepyline.cause'] != 'MISSING', 'sleepyline.cause'].drop_duplicates().sort_values()

    # Get original matched

    # already_fails_stably = 'AlreadyFailsStably AlreadyFailsStably'
    matched_original = pd.read_csv(matched_failures_slines).fillna(0)
    matched_original = matched_original.loc[matched_original['failureMessage'] != ('SleepyTimeOut(ProbableDeadlock)')]

    #matched_original_obo_failures = matched_original.copy().loc[~matched_original['FailConfigs.flakerake-obo'].isna(), ['failureID', 'test']].drop_duplicates()
    #print(f'unique obo failures = {len(matched_original_obo_failures)}')

    matched_original_bis_failures = matched_original.copy().loc[matched_original['flakerake'] > 0, ['failureID', 'test']].drop_duplicates()
    matched_orig_bis_tests = matched_original.copy().loc[matched_original['flakerake'] > 0, ['test']].drop_duplicates()
    print(f'unique bis failures = {len(matched_original_bis_failures)}')

    # matched_orig_fails_stably = matched_original.loc[matched_original['FailConfigs.flakerake'] == already_fails_stably, :]
    # matched_orig_fails_stably_tests = matched_orig_fails_stably.copy()[['test']].drop_duplicates()
    # matched_orig_fails_stably_failures = matched_orig_fails_stably.copy()[['test', 'failureID']]

    # matched_orig_bis_tests = matched_original.loc[~matched_original['FailConfigs.flakerake'].isna(), 'test'].drop_duplicates()
    #matched_orig_bis_tests = pipe_in_tid_df.loc[pipe_in_tid_df['method'] == 'BIS', ['test']].drop_duplicates()

    matched_unpacked = pd.read_csv('./scratch/flakerake-thread-lines-meta-next-pipe-in-tid_no-thread-trace.csv')
    # From here on out, only use what's in matched
    matched_unpacked = matched_unpacked.loc[matched_unpacked['failureID'] != 'MAXIMAL_CONFIG', :]
    matched_unpacked = matched_unpacked.loc[matched_unpacked['failureID'] != 'MIN_BUT_MISSING_FROM_MATCHED', :]
    matched_unpacked = matched_unpacked.loc[matched_unpacked['sleepyline'] != 'MISSING', :]

    # matched_bis = matched_unpacked.copy().loc[matched_unpacked['method'] == 'BIS', :]
    # matched_bis_tests = matched_bis.copy()[['test']].drop_duplicates()
    # matched_bis_failures = matched_bis.copy()[['failureID']].drop_duplicates()

    topn_causes['tests.proportion'] = topn_causes['test.count'] / len(matched_orig_bis_tests)
    topn_causes['failureID.proportion'] = topn_causes['failureID.Uniq.Count'] / len(matched_original_bis_failures)

    def get_correlate_top_n_causes():

        causes = (topn_causes.copy()['sleepyline.cause'])
        l_causes = (list(causes))

        bis_corr_topn = bis_corr[l_causes]
        bis_corr_topn = bis_corr_topn.transpose()[l_causes]

        return bis_corr_topn

    df_top_corr = report_most_bis_correlated(get_correlate_top_n_causes())

    # # Now do the above for only size 1 leaves
    # # NOT UNIQ
    # causeToConfigFlaggedAPI = pipe_in_tid_df.copy()[['method', 'test', 'failureID', 'configIdx', 'sleepyline.cause', 'sleepyline']].drop_duplicates()
    # # Get sizes
    # min_sizes = pd.read_csv('./scratch/sline.Min-size.csv')
    # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.merge(min_sizes)
    # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sline.size'] == 1, :]

    # causeToConfigNonFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] != 'FLAGGED_API', ['method', 'failureID', 'configIdx', 'sleepyline']]
    # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] == 'FLAGGED_API', ['method', 'failureID', 'configIdx', 'sleepyline']]

    # # Merge with flagged api causes
    # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.merge(flagged_api_to_line)
    # causeToConfigFlaggedAPI = pd.concat([causeToConfigFlaggedAPI, causeToConfigNonFlaggedAPI])

    # # get only those causes that are topn
    # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] in all_causes, :]

    # # Set them to zero
    # for cause in all_causes:
    #     causeToConfigFlaggedAPI[cause] = 0

    # # Set them that match to 1
    # for cause in all_causes:
    #     causeToConfigFlaggedAPI.loc[causeToConfigFlaggedAPI['sleepyline.cause'] == cause, cause] = 1

    # # THESE ARE BY CONFIG AND TEST DO NOT MAKE THEM UNIQ, we want configs for each test
    # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.drop(columns=['sleepyline.cause'])
    # causeToConfigFlaggedAPI = causeToConfigFlaggedAPI.groupby(['method', 'failureID', 'configIdx', ]).sum().reset_index().drop(columns=['configIdx', ])

    # Make alphabetical by swapping
    def _swap_cols_maybe(x):
        left_col = x[0]
        right_col = x[1]

        min_api = min(x[0], x[1])
        max_api = max(x[0], x[1])

        # Special cases to make latex look pretty I guess.
        if ('/' in left_col and '/' in right_col):
            left_clazz_path = left_col.split('.')[0]
            right_clazz_path = right_col.split('.')[0]

            left_col_clazz = left_clazz_path.split('/')[-1]
            right_col_clazz = right_clazz_path.split('/')[-1]

            if left_col_clazz <= right_col_clazz:
                print(f'min_clazz1={left_col_clazz}')
                min_api = left_col
                max_api = right_col
            else:
                print(f'min_clazz2={right_col_clazz}')
                min_api = right_col
                max_api = left_col

            print(f'min_api={min_api}')

        elif ('RUNNABLE_CALLABLE_START' in min_api):
            min_api = max_api
            max_api = 'RUNNABLE_CALLABLE_START'
        elif ('MONITOREXIT' == min_api and 'SYNCHRONIZED_METHOD_ENTER' == max_api):
            min_api = max_api
            max_api = 'MONITOREXIT'

        x[0] = min_api
        x[1] = max_api
        return x

    df_top_corr = (df_top_corr.apply(_swap_cols_maybe, axis=1))

    # Do latex transform
    # Adjust precision
    precision = 2
    topn_causes = topn_causes.round(decimals=precision)

    write_csv(df_top_corr, 'df_top_corr.csv', index=False)

    # Sort appropriately
    # Sort by unique Failure IDs then by test count
    print(topn_causes.columns)
    topn_causes = topn_causes.sort_values(by=['test.count', 'failureID.Uniq.Count'], ascending=False)

    topn_causes['proportion'] = topn_causes['proportion'].apply(lambda x: f'({x:.2f}\\%)')
    topn_causes['proportion'] = topn_causes['proportion'].apply(lambda x: x.replace(r'0.', '', 1))

    # Correlation gets rounded
    df_top_corr['Correlation'] = df_top_corr['Correlation'].apply(lambda x: f'{x:.2f}')
    df_top_corr['Correlation'] = df_top_corr['Correlation'].apply(lambda x: x.replace(r'0.', '.', 1))

    df_top_corr = df_top_corr.round(decimals=precision)

    topn_causes['tests.proportion'] = topn_causes['tests.proportion'].apply(lambda x: f'({x:.2f}\\%)')
    topn_causes['tests.proportion'] = topn_causes['tests.proportion'].apply(lambda x: x.replace(r'0.', '', 1))

    topn_causes['failureID.proportion'] = topn_causes['failureID.proportion'].apply(lambda x: f'({x:.2f}\\%)')
    topn_causes['failureID.proportion'] = topn_causes['failureID.proportion'].apply(lambda x: x.replace(r'0.', '', 1))

    # Combine columns
    spaces = '   '
    topn_causes['test.count'] = topn_causes['test.count'].apply(lambda x: f'{x}{spaces}') + topn_causes['tests.proportion']
    topn_causes['config.Count'] = topn_causes['config.Count'].apply(lambda x: f'{x}{spaces}') + topn_causes['proportion']
    topn_causes['failureID.Uniq.Count'] = topn_causes['failureID.Uniq.Count'].apply(lambda x: f'{x}{spaces}') + topn_causes['failureID.proportion']

    def _replace_cause_with_latex(cause):
        return r'\Use{' + cause + r'}'

    topn_causes['sleepyline.cause'] = (topn_causes['sleepyline.cause'].apply(_replace_cause_with_latex))

    # Rename to cause
    df_top_corr.rename(inplace=True, columns={'API': 'sleepyline.cause'})
    df_top_corr['sleepyline.cause'] = (df_top_corr['sleepyline.cause'].apply(_replace_cause_with_latex))

    # Re order columns
    topn_causes = topn_causes[[
        'sleepyline.cause',
        'test.count',
        'failureID.Uniq.Count',
        'config.Count',
    ]]

    write_csv(topn_causes, 'demo.csv', index=False)

    latex_col_map = {}
    for col in topn_causes.columns:
        latex_col_map[col] = r'\Use{' + col + r'}'
    topn_causes.rename(inplace=True, columns=latex_col_map)
    df_top_corr.rename(inplace=True, columns=latex_col_map)

    write_csv(topn_causes, 'bis_topn_causes.csv', index=False)
    with pd.option_context("max_colwidth", 1000):
        with open('bis_topn_causes.tex', 'w') as fd:
            fd.write(topn_causes.to_latex(escape=False, index=False))
        with open('bis_topn_causes_corr.tex', 'w') as fd:
            fd.write(df_top_corr.to_latex(escape=False, index=False))


def safety_checks():
    out = './characteristics/flakerake-thread-lines-meta-next.csv'
    out_df = pd.read_csv(out)
    matched_df = get_unpacked_matched_failures()

    # Check tests
    matched_test = matched_df[['test']]
    out_test = out_df[['test']]
    matched_test.drop_duplicates(inplace=True)
    out_test.drop_duplicates(inplace=True)
    print(f'matched uniq test = {len(matched_test)}')
    print(f'out uniq test = {len(out_test)}')
    merged_matched_out_test = pd.merge(matched_test, out_test, indicator=True, how='outer')
    write_csv(merged_matched_out_test, 'meta-test-canary.csv')

    # Check threads
    out_threads = out_df['thread.id']
    out_threads.drop_duplicates(inplace=True)

    matched_bis_threads = matched_df[['Thread.BIS']]
    matched_obo_threads = matched_df[['Thread.OBO']]

    matched_bis_threads.rename(columns={'Thread.BIS': 'thread.id'}, inplace=True)
    matched_obo_threads.rename(columns={'Thread.OBO': 'thread.id'}, inplace=True)

    matched_threads = pd.concat([matched_bis_threads, matched_obo_threads])
    matched_threads.drop_duplicates(inplace=True)

    print(f'matched uniq threads = {len(matched_threads)}')
    print(f'out uniq threads = {len(out_threads)}')
    merged_matched_out_threads = pd.merge(matched_threads, out_threads, indicator=True, how='outer')
    write_csv(merged_matched_out_threads, 'meta-threads-canary.csv')

    # check failure configs
    matched_bis_configs = matched_df[['Thread.BIS', 'SleepyLines.BIS', 'test', 'matchedIdx']]
    matched_bis_configs.drop_duplicates(inplace=True)
    matched_obo_configs = matched_df[['Thread.OBO', 'SleepyLines.OBO', 'test', 'matchedIdx']]
    matched_obo_configs.drop_duplicates(inplace=True)

    write_csv(matched_bis_configs, 'matched_bis_config-canary.csv')

    out_min_configs = out_df[out_df['sline.Min'] == 'True'][['configIdx', 'method', 'test', 'sline.Min']]
    out_min_configs.drop_duplicates(inplace=True)

    merged_matched_bis_lines = pd.merge(matched_bis_configs['SleepyLines.BIS'], out_df['sleepyline'], left_on='SleepyLines.BIS', right_on='sleepyline', indicator=True)
    merged_matched_bis_lines.drop_duplicates(inplace=True)
    write_csv(merged_matched_bis_lines, 'merged_bis_lines-canary.csv')

    write_csv(out_min_configs, 'out_min_configs-canary.csv')

    # Don't have a sensical canary table to make here.
    # out configs will have more actually, because matched failures condenses it.
    print(f'out min configs = {len(out_min_configs)}')
    print(f'matched min configs = {len(matched_bis_configs)} + {len(matched_obo_configs)} = {len(matched_bis_configs) + len(matched_obo_configs)}')

    # TODO unique test,failure,thread combos should be equal to unique test,failure,thread,slin.min is False


def get_maximal_scratch():
    out = './characteristics/flakerake-thread-lines-meta-next.csv'
    out_df = pd.read_csv(out)
    out_maximal = out_df[['test', 'method', 'sleepyline']]
    out_maximal = out_maximal.drop_duplicates()
    out_max_cnt = out_maximal.groupby(['test', 'method']).count()
    write_csv(out_max_cnt, './characteristics/sline.Max.Union.By-Method-size.csv')

    out_all_max = out_df[['test', 'sleepyline']]
    out_all_max = out_all_max.drop_duplicates()
    out_all_max_cnt = out_all_max.groupby('test').count()
    write_csv(out_all_max_cnt, './characteristics/sline.Max.Union-size.csv')


# def demo():

#     matched_failures = pd.read_csv('./matched-failures-all-sleepy-lines.csv')
#     matched_iso_fails = matched_failures.copy().loc[~matched_failures['rerun'].isna(), ['rerun', 'failureID']].drop_duplicates()
#     matched_iso_fails['rerun.proportion'] = matched_iso_fails['rerun'] / 10000
#     matched_iso_fails.sort_values('rerun.proportion', inplace=True)

#     rate = 0.001
#     coauthor_df1 = matched_iso_fails.loc[matched_iso_fails['rerun.proportion'] < rate, :]
#     coauthor_df1.to_csv('coauthor1.csv', index=False)

#     coauthor_df2 = matched_iso_fails.loc[matched_iso_fails['rerun'] == 1, :]
#     coauthor_df2.to_csv('coauthor2.csv', index=False)

#     print(matched_iso_fails.head())

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'canary':
            print('Doing safety checks')
            safety_checks()
        if sys.argv[1] == 'maximal':
            print('doing maximal')
            get_maximal_scratch()
        if sys.argv[1] == 'latex':
            print('doing latex reports')
            write_latex_tables()
        # if sys.argv[1] == 'demo':
        #     demo()
    else:
        print('Grabbing metadata')
        do_all()
