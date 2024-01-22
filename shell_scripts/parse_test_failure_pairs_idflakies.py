import os
import json
import os.path



def main():
    target_dir = os.getcwd()

    # Get original order so we can be sure we're only getting NOD failures
    # Currently we don't do this check any more
    # while 'original-order' not in os.listdir('./'):
    #     os.chdir('../')
    #
    # original_order = []
    # with open('original-order') as original_order_fd:
    #     for line in original_order_fd.readlines():
    #         original_order.append(line.strip())
    #
    # os.chdir(target_dir)

    pairs = []
    errors = []
    all_jsons = os.listdir(target_dir)
    for json_file in all_jsons:
        with open(json_file) as json_file_fd:
            parsed = json.load(json_file_fd)
            # if not parsed['testOrder'] == original_order:
            #     continue # See now commented code above.
            results = parsed['results']
            for key, val in results.items():
                if val['result'] != 'PASS':
                    stack_trace = val['stackTrace']
                    fail_lines = []

                    for part in stack_trace:
                        declaring_class = part['declaringClass']

                        test_package_prefix = '.'.join(key.split(r'.')[0:2])
                        if test_package_prefix == key:
                            # Special case packages where the prefix is of length 1.
                            test_package_prefix = test_package_prefix.split(r'.')[0]

                        if not declaring_class.startswith(test_package_prefix) or declaring_class.startswith('org.apache.maven'):
                            continue

                        method_name = part['methodName']
                        file_name = None
                        file_name = part.get('fileName', file_name)
                        line_number = part['lineNumber']
                        fail_line = '{}.{}({}:{})'.format(declaring_class, method_name, file_name, line_number)
                        fail_lines.append(fail_line)

                    fail_total = ' '.join(fail_lines)

                    pair = tuple([key, fail_total])
                    error = tuple([os.path.basename(json_file),key, fail_total])
                    if pair not in pairs:
                        pairs.append(pair)
                        errors.append(error)

    for err in errors:
        print('"{}","{}","{}"'.format(err[0], err[1], err[2]))

if __name__ == '__main__':
    main()
