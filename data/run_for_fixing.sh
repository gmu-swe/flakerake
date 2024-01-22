#!/bin/bash

if [[ $1 == "" ]]; then
    echo "arg1 - full path to the test file (eg. x.csv)"
    exit
fi

currentDir=$(pwd)
if [ ! -d "Result" ]; then
    mkdir "Result"
fi

if [ ! -d "Project" ]; then
    mkdir "Project"
fi
while read line
do
    if [[ ${line} =~ ^\# ]]; then
        echo "Line starts with Hash $line"
        continue
    fi 

    cd "$currentDir/Flaky-Test-Repair-Prototype/scripts/"
    bash find_APILineNumber.sh $line "Results/x.csv" 

    slug=$(echo $line | cut -d','  -f1)
    rootProj=$(echo "$slug" | cut -d/ -f 1)
    subProj=$(echo "$slug" | cut -d/ -f 2)
    sha=$(echo $line | cut -d','  -f2)
    module=$(echo $line | cut -d','  -f3)
    testName=$(echo $line | cut -d','  -f4)

    #mkdir "$currentDir/Result/$testName"
    echo "NOW RUNNING FLAKERAKE"
    cd "$currentDir/Project"

    if [[ ! -d $rootProj ]]; then
        git clone "https://github.com/$slug" "$slug"
        cd $slug 
        git checkout $sha 
    else
        cd $rootProj
        if [[ ! -d $subProj ]]; then
            cd -
            git clone "https://github.com/$slug" "$slug"
            cd $subProj 
            git checkout $sha 
        else 
            cd $subProj 
        fi
    fi

    echo "TestMethod" >> "x1.csv"
    echo "$testName" >> "x1.csv"
    data_loc=$(pwd)

    if [[ $module == "." ]]; then
        mkdir "BF_data"
        cp "$currentDir/Flaky-Test-Repair-Prototype/scripts/Locations/APILineNumber-$subProj-$testName-1.txt" "BF_data/"
        cp "$currentDir/Flaky-Test-Repair-Prototype/scripts/Locations/MethodList-$subProj-$testName-1.txt" "BF_data/"
        cp "$currentDir/Flaky-Test-Repair-Prototype/scripts/Locations/whitelist-$subProj-$testName-1.txt" "BF_data/"
        $PYTHON_FLAKY_BIN ${FLAKY_HOME}shell_scripts/findFlakySleeps_with_reproduction_and_fix.py --reproduceFailureFile "/logs/results/flakeRake/2021-12-14/$testName/report/flakeRakeInput.csv_minimal_sleep_report.csv" --whitelist "BF_data/whitelist-$subProj-$testName-1.txt" --fixDelayLocation "BF_data/APILineNumber-$subProj-$testName-1.txt" 

    else
        cd $module
        mkdir "BF_data"
        module_replace_directory_structure=$(echo $module | sed 's/\//./g')
        #echo $module_replace_directory_structure
        cp "$currentDir/Flaky-Test-Repair-Prototype/scripts/Locations/APILineNumber-${module_replace_directory_structure}-$testName-1.txt" "BF_data/"
        cp "$currentDir/Flaky-Test-Repair-Prototype/scripts/Locations/MethodList-${module_replace_directory_structure}-$testName-1.txt" "BF_data/"
        cp "$currentDir/Flaky-Test-Repair-Prototype/scripts/Locations/whitelist-${module_replace_directory_structure}-$testName-1.txt" "BF_data/"
        $PYTHON_FLAKY_BIN ${FLAKY_HOME}shell_scripts/findFlakySleeps_with_reproduction_and_fix.py --reproduceFailureFile "/logs/results/flakeRake/2021-12-14/$testName/report/flakeRakeInput.csv_minimal_sleep_report.csv" --whitelist "BF_data/whitelist-$subProj-$testName-1.txt" --fixDelayLocation "BF_data/APILineNumber-$module_replace_directory_structure-$testName-1.txt" 
    fi
	cd $currentDir
    #rm -rf "Project-Old-Proj/$rootProj"
done < $1
