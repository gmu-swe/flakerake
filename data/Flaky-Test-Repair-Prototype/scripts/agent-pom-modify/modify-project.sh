#!/bin/bash

if [[ $1 == "" ]]; then
	echo "arg1 - the slug of the project"
	exit
fi

project_path=$1

currentDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
THE_PATH_TO_AGENT_JAR=$currentDir"/../../agent/target"
ARG_LINE="-javaagent:$THE_PATH_TO_AGENT_JAR/agent-0.1-SNAPSHOT.jar"

crnt=`pwd`
working_dir=`dirname $0`
#project_path=$1

cd ${project_path}
project_path=`pwd`
cd - > /dev/null

cd ${working_dir}

javac PomFile.java
find ${project_path} -name pom.xml | grep -v "src/" | java PomFile ${ARG_LINE}
rm -f PomFile.class

cd ${crnt}
