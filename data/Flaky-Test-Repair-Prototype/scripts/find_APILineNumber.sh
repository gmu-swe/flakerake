#!/usr/bin/env bash
if [[ $1 == "" || $2 == "" ]]; then
    echo "arg1 - full path to the test file (eg. tmp.csv)"
    echo "arg2 - relative path to the output file (eg. Results/output.csv)"
    exit
fi

currentDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

inputProj=$currentDir"/projects"
outputDir="$2"

if [ ! -d "projects" ] 
then
    mkdir ${inputProj}
fi

if [ ! -d "logs" ] 
then
    mkdir "logs"
fi

if [ ! -d "Results" ] 
then
    mkdir "Results"
fi

if [ ! -d "Locations" ] 
then
    mkdir "Locations"
fi

echo -n "Module-Name" >> "$currentDir/$outputDir"
echo -n ",SHA" >> "$currentDir/$outputDir"
echo -n ",Module" >> "$currentDir/$outputDir"
echo -n ",Test-Name" >> "$currentDir/$outputDir"

echo -n ",Delay-Line-Num[Delay Amount]" >>  "$outputDir"
echo  ",TestPass(1=testpass)" >>  "$outputDir"

line=$1
if [[ ${line} =~ ^\# ]]; then
    echo "Line starts with Hash $line"
    continue
fi
slug=$(echo $line | cut -d',' -f1)
sha=$(echo $line | cut -d',' -f2)
module=$(echo $line | cut -d',' -f3)
testName=$(echo $line | cut -d',' -f4)
rootProj=$(echo "$slug" | cut -d/ -f 1)
subProj=$(echo "$slug" | cut -d/ -f 2)

if [[ ! -d ${inputProj}/${rootProj} ]]; then
    git clone "https://github.com/$slug" $inputProj/$slug
fi

cd $inputProj/$slug
git checkout ${sha}

if [[ "$slug" == "doanduyhai/Achilles" ]]; then
    sed -i 's~http://repo1.maven.org/maven2~https://repo1.maven.org/maven2~g' pom.xml
else
    echo "Strings are not equal."
fi  

echo -n "${slug}" >> "$currentDir/$outputDir"
echo -n ",${sha}" >> "$currentDir/$outputDir"
echo -n ",${module}" >> "$currentDir/$outputDir"
echo -n ",${testName}" >> "$currentDir/$outputDir"

if [[ $module != "." ]]; then
    projName=$(sed 's;/;.;g' <<< "$module-$testName")
    echo "**************************** $projName"
 else   
    projName=$(sed 's;/;.;g' <<< $subProj-$testName)
fi
#maven run in normal settings to keep record time and failure

cd $currentDir"/agent-pom-modify"
bash modify-project.sh $inputProj/$slug

cd $inputProj/$slug
mvn clean

mvn install -DskipTests #-pl $module -am
find -name "*.class" | grep -v Tests | sed 's;.*target/classes/;;'| sed 's;/;.;g' | sed 's;.class$;;' > whitelist.txt
#To remove the test-classes
sed -i '/test-classes/d' whitelist.txt   

if [[ "$slug" == "TooTallNate/Java-WebSocket" ]]; then
    sed -i '/org.java_websocket.server.WebSocketServer/d' "whitelist.txt"
fi

if [[ "$slug" == "square/okhttp" ]]; then
    sed -i '/com.squareup.okhttp.Request/d' "whitelist.txt"
fi

if [[ "$slug" == "alibaba/fastjson" ]]; then
    sed -i '/com.alibaba.json.bvt.parser.deser.AbstractSerializeTest/d' "whitelist.txt"
fi


if [[ "$slug" == "square/okhttp" ]]; then
    sed -i '/com.squareup.okhttp.Request/d' "whitelist.txt"
    sed -i '/com.squareup.okhttp.internal.spdy.SpdyConnection/d' "whitelist.txt"
    
fi  

if [[ "$slug" == "apache/httpcore" ]]; then
    sed -i '/org.apache.http.message.BasicLineParser/d' "whitelist.txt"
    sed -i '/org.apache.http.message.BasicLineFormatter/d' "whitelist.txt"
    sed -i '/org.apache.http.message.BasicHeaderValueParser/d' "whitelist.txt"
fi 

mv whitelist.txt "$currentDir/Locations/whitelist-${projName}-1.txt"

#1st Run, To Find concurent method list

for run in {1..1}; do
    mvn test -pl $module -Dwhitelist="$currentDir/Locations/whitelist-$projName-1.txt" -DfindAPI -Dtest=$testName &> "$currentDir/logs/log"
    if [ -f "$(find . -name "MethodList.txt")" ]; then
        resultMethods=$(find . -name "MethodList.txt") 
        mv $resultMethods "methodlist-$projName-FlakeDelay-Run-$run.txt"
        cat "methodlist-$projName-FlakeDelay-Run-$run.txt" > "methodlist.txt"
        rm "methodlist-$projName-FlakeDelay-Run-$run.txt" 
    fi
done
sort -u -o "methodlist.txt" "methodlist.txt"
mv  "methodlist.txt" "$currentDir/Locations/MethodList-$projName-1.txt"

mvn test -pl $module -Dwhitelist="$currentDir/Locations/whitelist-$projName-1.txt" -DallAPI="$currentDir/Locations/MethodList-$projName-1.txt" -Dtest=$testName &> "$currentDir/logs/log1"

#echo $(pwd)
mv $(find -name "ResultLocations.txt") "$currentDir/Locations/APILineNumber-${projName}-1.txt"


#mvn test -pl $module -Dwhitelist="$currentDir/Locations/whitelist-$projName.txt" -Dlocations="$currentDir/Locations/APILineNumber-$projName.txt"  -Dtest=$testName &> "$currentDir/logs/log2"
 

#cd $currentDir

#bash run-one-by-one-delay.sh "$slug,$sha,$module,$testName" "Locations/" "$currentDir"
echo "" >> "$currentDir/$outputDir"
cd $currentDir
#rm -rf "$inputProj/$rootProj"

