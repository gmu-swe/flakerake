import argparse
import glob
import re
import csv
import os
import xml.etree.ElementTree as ET
import itertools
import sys

import boto3
import tarfile

import shutil

import csv_utils

# get a hold of the flaky bucket.

s3 = boto3.resource('s3')
bucket = s3.Bucket('flakylogs')
# os.system('mkdir -p aws-archives')

aws_report_dir = os.path.join(os.getenv('HOME'), 'flaky-test-aws')

# Order matters here
AWS_PREFIX_DIR_TO_CHECK = ['logsreruns', 'logs', 'logsfirst2k']


def get_fail_line_generator(error_text, package_prefix):
    """
    :param error_text:
    :param package_prefix:
    :return:  any error lines that begin with the package prefix.
    """
    # # Special case: see 'zxing-zxing' 'com.google.zxing.aztec.encoder.EncoderTest#testAztecWriter' "3471"
    # Now handled by below code
    # if 'com.google.zxing.FormatException: null' == error_text.strip():
    #     yield 'com.google.zxing.FormatException: null'
    #     return

    # Special case no lines in failure
    ats = re.findall(r'\s*at ', error_text.strip())
    if not ats:
        yield error_text.strip()
        return


    whitespace_pattern = re.compile(r'\s+')
    for line in error_text.split('\n'):
        trimmed_line = re.sub(whitespace_pattern, '', line)
        if not trimmed_line.startswith('at'):
            # We only want line numbers
            continue
            # Remove the prefix at
        trimmed_line = re.sub(r'^at', '', trimmed_line)
        # Skip maven things
        maven_prefix = 'org.apache.maven'
        if trimmed_line.startswith(maven_prefix):
            continue
        if trimmed_line.startswith(package_prefix):
            yield trimmed_line


def aws_tgz_getter(project, flaky_log_id):
    key_suffix = "{}/{}.tgz".format(project, flaky_log_id)
    download_dir_path = os.path.join(aws_report_dir, project)
    download_file_path = os.path.join(download_dir_path, "{}.tgz".format(flaky_log_id))
    # Download archive from aws
    if not os.path.exists(download_file_path):
        os.system("mkdir -p {}".format(download_dir_path))
        for aws_prefix_dir in AWS_PREFIX_DIR_TO_CHECK:
            key_prefix = "{}/".format(aws_prefix_dir)
            try:
                bucket.download_file('{}{}'.format(key_prefix, key_suffix), download_file_path)
                break  # We stop now in order not to improperly overwrite archive.
            except Exception as e:
                print(str(e))
    return download_file_path


def get_test_result_xml(project, test_method, flaky_log_id, cleanup_after=False, tgz_getter_fn=aws_tgz_getter):
    download_file_path = tgz_getter_fn(project, flaky_log_id)

    # Extract tgz if it isn't already.
    extracted_file_path = download_file_path + ".extracted"
    if not os.path.exists(extracted_file_path):
        with tarfile.open(download_file_path) as archive:
            archive.extractall(extracted_file_path)
    # Get test xml file referred to by test_method.
    failing_test_xml = None
    for root, dirs, files in os.walk(extracted_file_path):
        for file in files:
            if file == "TEST-{}.xml".format(test_method[0:test_method.find("#")]):
                failing_test_xml = os.path.join(root, file)
                break

    if not failing_test_xml:
        raise FileNotFoundError(f'No XML could be found for {project} {test_method} {flaky_log_id}')

    with open(failing_test_xml) as failing_test_xml_fd:
        output_xml_str = ''.join(failing_test_xml_fd.readlines())

    # Cleanup creates dirs as needed
    if cleanup_after:
        shutil.rmtree(extracted_file_path)
        shutil.rmtree(aws_report_dir, project)

    return output_xml_str


def parse_failure_trace_from_xml_str(test_method, failing_test_xml_str):
    fail_lines = []

    root = ET.fromstring(failing_test_xml_str)
    for testCase in root.findall('testcase'):
        if testCase.attrib['name'] == test_method[test_method.find("#") + 1:]:

            package_prefix = '.'.join(testCase.attrib['classname'].split(r'.')[0:2])

            # Special case: see "spring-projects-spring-boot" 'sample.data.gemfire.SampleDataGemFireApplicationTests#testGemstonesApp' "4454"
            if testCase.attrib['name'] == "testGemstonesApp":
                package_prefix = 'org.springframework'

            for failure in itertools.chain(testCase.iter('flaky_fail_attempt'), testCase.iter('error'),
                                           testCase.iter('failure')):

                fail_generator = get_fail_line_generator(failure.text, package_prefix)
                for fail_line in fail_generator:
                    fail_lines.append(fail_line)
                break  # Just stop since we found the failing lines.
            if not fail_lines:
                # Go and check sysout
                for output in testCase.iter('system-err'):  # should be singleton
                    for fail_line in get_fail_line_generator(output.text, package_prefix):
                        fail_lines.append(fail_line)

    return ' '.join(fail_lines)


def get_stack_trace(project, test_method, flaky_log_id, cleanup_after=False, failing_test_xml_str=None):
    # Parse flaky_fail_attempt as text from xml file.
    if not failing_test_xml_str:
        failing_test_xml_str = get_test_result_xml(project, test_method, flaky_log_id, cleanup_after=cleanup_after)
    return parse_failure_trace_from_xml_str(test_method, failing_test_xml_str)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tool for parsing failure strings from Flake Flagger aws logs.'
                                                 'Checks a local cache before doing network IO')
    parser.add_argument("project", help='FlakeFlagger project col')
    parser.add_argument("test_method", help='FlakeFlagger test col')
    parser.add_argument("failure_id", type=int, help='FlakeFlagger failure id col, if not failing id will return nothing.')
    parser.add_argument("--abstract_failure", action='store_true')
    parser.add_argument("--base64_encode", action='store_true')
    args = parser.parse_args()

    project_arg = args.project
    test_method_arg = args.test_method
    failure_id_arg = args.failure_id
    abstract_failure_arg = args.abstract_failure
    base64_encode_failure_arg = args.base64_encode

    if abstract_failure_arg:
        result = get_stack_trace(project_arg, test_method_arg, failure_id_arg)
    else:
        result = get_test_result_xml(project_arg, test_method_arg, failure_id_arg)

    result = csv_utils.flake_rake_base64_encode(result) if base64_encode_failure_arg else result
    print(result)

