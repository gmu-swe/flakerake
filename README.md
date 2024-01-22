# FlakeRake Tool Instructions

## Experimental Artifact
An artifact including all of the output from the ICST 2024 paper describing FlakeRake is available on Zenodo at [https://zenodo.org/doi/10.5281/zenodo.7041599](https://zenodo.org/doi/10.5281/zenodo.7041599)

## Installation (Tested on Ubuntu 16.04.7 LTS)

These instructions "should" be idempotent.

1. Run `export FLAKY_HOME="<PATH_TO_FLAKE_FAKE>"`
1. Run `export JAVA_FLAKY_HOME="<PATH_TO_YOUR_CHOSEN_JDK>"`\
FlakeRake has historically used this JDK: \
[jdk-8u102.tgz](https://drive.google.com/file/d/1UcVgqJiXiXD9MJSrxQ3QHFLNV1mQaOOO "JDK 1.8.102")
1. Run `sudo -E bash $FLAKY_HOME/shell_scripts/node-install-deps`
1. Run `. $HOME/.profile`
1. Run `mvn -f $FLAKY_HOME install -DskipTests`
1. Append `export MAVEN_REPO=<SOME_PATH>/.m2/repository` to `$HOME/.profile`
1. [Optional] Setup aws creds and boto3 to access aws s3 flaky impact bucket


## Usage

0. Besides this readme, investigate usage by running
```
$PYTHON_FLAKY_BIN $FLAKY_HOME/shell_scripts/findFlakySleeps.py -h
```

1. Navigate to the directory of a flaky module under study.
Note: This is not always the root directory of a project.

2. Create an CSV File with at least 1 column `TestMethod`

Example
```csv
TestMethod
ch.qos.logback.core.AsyncAppenderBaseTest#workerShouldStopEvenIfInterruptExceptionConsumedWithinSubappender
```

FlakeRake will analyze every test method.

3. Run the following command (This may minutes to hours depending on the test)
`$PYTHON_FLAKY_BIN $FLAKY_HOME/shell_scripts/findFlakySleeps.py --testMethodsFile <PATH TO FILE>`

4. When finished, a reports of the following with the prefix `<INPUT FILE NAME>` will be present in `./sleepy-records/report/`

* `{INPUT FILE NAME}_minimal_sleep_report.csv` - SleepyLine Reproduction Data (Answers: how do I cause a failure stably?)
  * Columns:
	* Project\_Git_URL - The git (Github so far) remote repo (matches input csv value)
	* Git_SHA - The git SHA that was tested (matches input csv value)
	* TestMethod - Test method being analyzed
	* Minutes - The cumulative minutes to analyze the thread
	* Thread - The Thread identifier, shasum of stacktrace and count
	* SleepyLines - Space separated list of lines to sleep thread at to reproduce failure for thread.
	* Failure - Is ascii encoded of the form `<Exception Line>FlakeRakeB64StackTrace=<Base64 Encoded StackTrace>`
	Abstracted to remove lines not specific to the project.
* `{INPUT FILE NAME}_cause_to_interception_report.csv` - Cause to sleep insertion (Answers: why did we sleep here?)
  * Columns : NOTE that this only includes lines that were actually slept at.
	* TestMethod - The test being run
	* Thread - The Thread identifier, shasum of stacktrace and count
	* SleepyRunId - The run identifier (count) for doing a sleepy run with `TestMethod`
	* Cause - The reason FlakeRake chose to insert a sleep here
	* Interception - The line where a sleep is inserted

* `{INPUT FILE NAME}_sha_to_stacktrace_report.csv` - Thread SHA identifier to their forking threads stack trace (Answers: How do I identify a thread?)
  * Columns:
	* Thread - The Thread identifier, shasum of stacktrace and count (`<main>` is special case)
	* StackTrace - The stacktrace of the forking thread when forking

* `{INPUT FILE NAME}_minimal_exploration_report.csv` - How much time we spent exploring and which candidate lines existed
  * Columns :
	* TestMethod - The test being run
	* Thread - The Thread identifier, shasum of stacktrace and count
	* Failure - The failure
	* EpochSeconds - Timestamp in seconds as epoch time
	* GlobalExploreID - ID for minimalization exploring, starts at 1 and increases with every test,tid,sleepylines tried

reproducing failures will be in `./sleepy-records/report/{INPUT FILE NAME}_minimal_sleep_report.csv`

## Results
Resulting Report Columns from `--testMethodsFile`:
* Project - The project containing flaky tests, also in AWS flaky archives.
* TestMethod - The test method that is flaky.
* FirstFailingID - From AWS flaky archives, the first run where a flaky test fails.
* Minutes - The minutes it took to do the analysis to create this row's data.
* Thread - The unique-ish (See `Wrapper.java`) identifier for a thread that gets created during a test.
* Failure - Is ascii encoded of the form `<Exception Line>FlakeRakeB64StackTrace=<Base64 Encoded StackTrace>`
* AWSFailure - The flaky failure in AWS associated with this project and test method.

Resulting Report Columns from `--reproduceFailureFile`:
* TestMethod - The test method we're attempting to stably reproduce a failure in.
* Thread - The thread we're sleeping when reproducing a failure.
* SleepyLines - The lines we're sleeping at.

## Try it out

1. Navigate to `$FLAKY_HOME/integration-test`

2. Run `$PYTHON_FLAKY_BIN $FLAKY_HOME/shell_scripts/findFlakySleeps.py --testMethodsFile ./all_easysource_testmethods.csv --logging debug --runs 1` (this may take some time for all tests)

3. Investigate reports and logs in `./sleepy-records/report` and `./sleepy-records/logs`, respectively.


### Expected Output

One will see the aforementioned tables.
Some rows will have a failure of `NoFail`, this is expected as some threads will no failure.
The `test.edu.gmu.edu.EasySourceTest#testOOMError` rows will have a Failure `FAILURE_THAT_COULD_NOT_BE_LOGGED`.
This is expected, as FlakeRake cannot extract that failure stack trace.


## Adding a SleepyLines Minimalization Method

To add a method for minimilizing the sleepy lines besides the default `bisection` follow below steps:

1. Add function to `$FLAKY_HOME/shell_scripts/findFlakysleeps.py` by following the current `bisection` as a guide.

2. In that same script, add your function to `minimal_sleeps_method_function_map` dictionary

3. Now run the script with `--minimalizing_method MINIMALIZING_METHOD`
