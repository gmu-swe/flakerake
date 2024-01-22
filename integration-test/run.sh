#!/bin/bash
../apache-maven-3.5.2-phosphor/bin/mvn -Dphosphor.sources=../config-files/demo/sources -Dphosphor.sinks=../config-files/demo/sinks -Dphosphor.taintThrough=../config-files/demo/taintThrough test

