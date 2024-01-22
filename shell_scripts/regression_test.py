# Quick and dirty script for running regression comparsions
import argparse
import csv
import os

import compare_stack_traces


def assert_supersubset_reports(superset_path, subset_path):
    def get_failure_set(csv_path):
        csv_failures = set()
        row_num = 0
        with open(csv_path, 'r') as csv_fd:
            row_dict_reader = csv.DictReader(csv_fd, dialect='unix')
            for row in row_dict_reader:
                row_num += 1
                # print(row_num)
                # print(csv_path)
                # print(row)
                if row['TestMethod'] and row['Failure']:
                    failure = tuple([row['TestMethod'].strip(),
                                     row['Failure'].strip()])
                    csv_failures.add(failure)
        return csv_failures

    superset_fails = get_failure_set(superset_path)
    subset_fails = get_failure_set(subset_path)

    if (superset_fails.issuperset(subset_fails)):
        return f'{superset_path} is a superset of {subset_fails}'

    subset_diff = subset_fails.difference(superset_fails)

    def get_row_failure_similarity_measures(missing_failure, same_test_method=True):
        """

        :param same_test_method:
        :param missing_failure: testmethod, failure pair
        :return: testmethod, most similar failure, top trace match, bottom trace match
        """
        missing_test = missing_failure[0]
        missing_test_failure_trace_str = missing_failure[1]
        missing_test_failure_trace_parts = missing_test_failure_trace_str.split(' ')

        # List of tuples consisting of (testmethod, failure stacktrace str, top trace similarity, bottom trace similarity
        super_test_method_failure_similarities = []

        for super_test_method, super_failure in superset_fails:
            if same_test_method and super_test_method != missing_test:
                continue
            super_failure_parts = super_failure.split(' ')
            top_trace_matches, bottom_trace_matches, lcs = compare_stack_traces.compare_stack_traces(
                super_failure_parts,
                missing_test_failure_trace_parts
            )
            super_test_method_failure_similarities.append(
                [super_test_method, super_failure, top_trace_matches, bottom_trace_matches, lcs]
            )

        # Get the maximal similar stack traces
        # similarity here will be defined as (top_match + bottom_match) / (2 * total_trace compared)
        max_list = []
        #
        # # Get initial max, then compare against minimum and all those to min-list
        # def top_similarity(x):
        #     return len(x[2]) / len(missing_test_failure_trace_parts)
        #
        # def bottom_similarity(x):
        #     return len(x[3]) / len(missing_test_failure_trace_parts)
        #
        # def total_similarity(x):
        #     return (top_similarity(x) + bottom_similarity(x)) / 2

        out_rows = []
        for test, test_failure, top_match, bottom_match, lcs_match in super_test_method_failure_similarities:
            out_rows.append([test, test_failure, len(top_match), len(bottom_match), len(lcs_match),
                             len(missing_test_failure_trace_parts)])

        # initial_max = max(super_test_method_failure_similarities, key=total_similarity)
        #
        # initial_max.append(top_similarity(initial_max))
        # initial_max.append(bottom_similarity(initial_max))
        # initial_max.append(total_similarity(initial_max))

        print(out_rows)

        return out_rows

    missing_failures = list(subset_diff)
    missing_failures.sort()
    diff_report_name = f"{os.path.splitext(os.path.basename(superset_path))[0]}-{os.path.splitext(os.path.basename(subset_path))[0]}.csv"

    # Write the actual diff report
    print(f'Writing diff report to {diff_report_name}')
    with open(diff_report_name, 'w') as diff_report_fd:
        diff_report_fd.write('"TestMethod","Failure"\n')
        for test_method, failure in missing_failures:
            diff_report_fd.write(f"\"{test_method}\",\"{failure}\"\n")

    ## Most similar analysis should be put to other script ##
    # # Write for each missing test,failure pair, the closest matching failure, if there is a tie, write them both.
    # similar_failure_report_name = f"{os.path.splitext(diff_report_name)[0]}-most-similar-to-missing-failure.csv"
    # print(f'Writing most similar failure report to {similar_failure_report_name}')
    # with open(similar_failure_report_name, 'w') as similar_failure_report_name_fd:
    #     similar_failure_report_name_fd.write(
    #         '"TestMethod","Failure","MaximalSimilarFailure","TopSameCount","BottomSameCount","LCS","MissingFailureLength"\n')
    #     for test_method, failure in missing_failures:
    #         failure_similarity_measures = get_row_failure_similarity_measures(tuple([test_method, failure]))
    #         for measure in failure_similarity_measures:
    #             row = [
    #                 f"\"{test_method}\"",
    #                 f"\"{failure}\"",
    #                 f"\"{measure[1]}\"",
    #                 f"\"{measure[2]}\"",
    #                 f"\"{measure[3]}\"",
    #                 f"\"{measure[4]}\"",
    #                 f"\"{measure[5]}\"",
    #             ]
    #             similar_failure_report_name_fd.write(','.join(row) + '\n')
    #         # similar_failure_report_name_fd.write(
    #         #     f",\"{failure}\",\"{most_similar_failure[1]}\",\"{0}\".\"{0}\",\"{0}\"\n")

    print('Finished')


if __name__ == '__main__':
    # Computes a set diff of subset - superset
    parser = argparse.ArgumentParser()
    parser.add_argument("superset_report_path")
    parser.add_argument("subset_report_path")

    args = parser.parse_args()
    assert_supersubset_reports(args.superset_report_path, args.subset_report_path)
