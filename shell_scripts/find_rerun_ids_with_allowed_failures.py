import os
import shutil
import tarfile

import correlate_flaky_aws
import csv
import re
import sys
import time

# Assuming test_results.csv is in the same dir
banned_strings = ['sun.security.ssl.SSLSocketImpl.initHandshaker',
                  'sun.security.ssl.Handshaker.setSNIServerNames',
                  'java.lang.NoSuchMethodError',
                  'Network is unreachable',
                  'javax.net.ssl.SSLHandshakeException',
                  'java.net.UnknownHostException',
                  'test timed out',
                  'java.lang.ClassLoader.loadClass'
                  ]
banned_regex = re.compile('|'.join(banned_strings))


def _has_banned_failure(xml_str):
    return banned_regex.findall(xml_str)


def get_test_result_xml(project, test_method, flaky_log_id, cleanup_after=False):
    download_file_path = f'failing-test-reports-{project}.tgz'

    # Extract tgz if it isn't already.
    failing_test_xml = f'failingLogs/{project}/{flaky_log_id}/{test_method}.xml'
    with tarfile.open(download_file_path) as archive:
        # target = "TEST-{}.xml".format(test_method[0:test_method.find("#")])
        print(download_file_path)
        archive.extractall(download_file_path)

    # extracted_file_path = 'failingLogs'
    # # Get test xml file referred to by test_method.
    # failing_test_xml = None
    # for root, dirs, files in os.walk(f'{extracted_file_path}/{project}/{flaky_log_id}'):
    #     for file in files:
    #         if file == "TEST-{}.xml".format(test_method[0:test_method.find("#")]):
    #             failing_test_xml = os.path.join(root, file)
    #             break

    if not failing_test_xml:
        raise FileNotFoundError(f'No XML could be found for {project} {test_method} {flaky_log_id}')

    with open(failing_test_xml) as failing_test_xml_fd:
        output_xml_str = ''.join(failing_test_xml_fd.readlines())

    # Cleanup creates dirs as needed
    if cleanup_after:
        pass
        # shutil.rmtree(extracted_file_path)

    return output_xml_str


with open(f'interesting_failures.csv', 'w') as output_fd:
    csv_writer = csv.writer(output_fd, quoting=csv.QUOTE_ALL)
    csv_writer.writerow(['Project', 'TestMethod', 'FailingRunID', 'Failure'])

    try:
        archive_paths_of_failures = []
        with open(sys.argv[1]) as archive_paths_fd:
            for line in archive_paths_fd:
                archive_paths_of_failures.append(line.strip())
        for path in archive_paths_of_failures:
            with tarfile.open(path) as archive:
                for member in archive.getmembers():
                    if member.name.endswith(".xml"):
                        member_parts = member.name.split('/')
                        test_method = os.path.splitext(member_parts[-1])[0]
                        redo = ['org.apache.hadoop.hbase.client.TestFromClientSide#testPut',
                                'org.apache.maven.surefire.junit4.JUnit4Provider#com.github.jknack.handlebars.springmvc.MessageSourceHelperTest',
                                'com.google.zxing.aztec.encoder.EncoderTest#testAztecWriter',
                                'sample.data.gemfire.SampleDataGemFireApplicationTests#testGemstonesApp']
                        if test_method not in redo:
                            continue
                        archive.extract(member)
                        project = member_parts[1]
                        failing_run_id = int(member_parts[2])

                        with open(member.name) as failing_test_xml_fd:
                            output_xml_str = ''.join(failing_test_xml_fd.readlines())

                        if _has_banned_failure(output_xml_str):
                            continue
                        abstracted_failure_str = correlate_flaky_aws.parse_failure_trace_from_xml_str(test_method,
                                                                                                      output_xml_str)
                        csv_writer.writerow([project, test_method, failing_run_id, abstracted_failure_str])
                        output_fd.flush()
                    # Cleanup
                    shutil.rmtree('failingLogs', ignore_errors=True)
    except Exception as e:
        print(f'last working {path}')
        raise e

    # with open(sys.argv[1]) as test_results_fd:
    #     dict_reader = csv.DictReader(test_results_fd)
    #     for row in dict_reader:
    #         project = row['Project']
    #         test_method = row['Test']
    #         first_failing_run_id = int(row['FirstFailingRunID'])
    #         num_failing_runs = int(row['NumFailingRuns'])
    #         num_passing_runs = int(row['NumPassingRuns'])
    #         num_runs = num_failing_runs + num_passing_runs
    #
    #         if num_failing_runs <= 0:
    #             continue
    #
    #         # Starting from first failing id, look for allowed failure in each
    #         for count in range(first_failing_run_id, num_runs):
    #             try:
    #                 test_result_xml_str = get_test_result_xml(project, test_method, count, cleanup_after=True)
    #
    #                 has_banned_failure = _has_banned_failure(test_result_xml_str)
    #
    #                 abstracted_failure_str = correlate_flaky_aws.get_stack_trace(project, test_method, count)
    #
    #                 if not has_banned_failure and abstracted_failure_str:
    #                     abstracted_failure_str = correlate_flaky_aws.parse_failure_trace_from_xml_str(test_method,
    #                                                                                                   test_result_xml_str)
    #                     csv_writer.writerow([project, test_method, count, abstracted_failure_str])
    #                     output_fd.flush()
    #             except FileNotFoundError as e:
    #                 print(f'No log could be found for {project} {test_method} {count}')
    #                 continue
    #             except Exception as e:
    #                 print(f'failure for {project} {test_method} {count}')
    #                 raise e
