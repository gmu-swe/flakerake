# This script calcualtes the cost to run flakerake relative to the cost that it takes to run isolation 1000 rounds.
# Usage: bash calculate-runtimes.sh unique-failure-detection-time-by-method.csv

# https://github.com/TestingResearchIllinois/flake-rake/blob/master/unique-failure-detection-time-by-method.csv
# flakerake@flakerake2:~/flaky-impact/shell_scripts$ head unique-failure-detection-time-by-method.csv?token=GHSAT0AAAAAABSP7MDEVFGDDVIXKQBNCVUYYRQ74XA 
# ,test,flakerake-oboTime.TOTAL,flakerake-obo.Unique,flakerakeTime.TOTAL,flakerake.Unique,isolatedTime.TOTAL,isolatedRerun.Unique
# 0,ch.qos.logback.classic.net.SMTPAppender_GreenTest.LBCLASSIC_104,3448.7695207595825,1,3644.371575117111,1,2026.038,0

# To convert new format to an old format:
# for f in $(cat /experiment/flakerake/timing/combined_times.csv); do t=$(echo $f | cut -d, -f1); buf=$(echo $f | cut -d, -f2); bt=$(echo $f | cut -d, -f4); ouf=$(echo $f | cut -d, -f5); ot=$(echo $f | cut -d, -f7); iuf=$(echo $f | cut -d, -f8); it=$(echo $f | cut -d, -f10); echo ",$t,$ot,$ouf,$bt,$buf,$it,$iuf"; done | grep -v ,skipped, > unique-failure-detection-time-by-method-updated.csv 

timefile=$1

# obo did not find compared with the time for isolation for the same tests
obon=$( cut -d, -f1-4,7- $timefile | grep ",0,.*,.*$"  | cut -d, -f3 | tail -n +2 | paste -sd+ | bc -ql)
isolationobon=$(cut -d, -f1-4,7- $timefile | grep ",0,.*,.*$"  | cut -d, -f5 | tail -n +2 | paste -sd+ | bc -ql)

bisn=$( cut -d, -f1-2,5- $timefile | grep ",0,.*,.*$"  | cut -d, -f3 | tail -n +2 | paste -sd+ | bc -ql)
isolationbisn=$( cut -d, -f1-2,5- $timefile | grep ",0,.*,.*$"  | cut -d, -f5 | tail -n +2 | paste -sd+ | bc -ql)

# at least one configuration found
obof=$( cut -d, -f1-4,7- $timefile | grep -v ",0,.*,.*$"  | cut -d, -f3 | tail -n +2 | paste -sd+ | bc -ql)
isolationobof=$( cut -d, -f1-4,7- $timefile | grep -v ",0,.*,.*$"  | cut -d, -f5 | tail -n +2 | paste -sd+ | bc -ql)

bisf=$( cut -d, -f1-2,5- $timefile | grep -v ",0,.*,.*$"  | cut -d, -f3 | tail -n +2 | paste -sd+ | bc -ql)
isolationbisf=$( cut -d, -f1-2,5- $timefile | grep -v ",0,.*,.*$"  | cut -d, -f5 | tail -n +2 | paste -sd+ | bc -ql)

# all 
oboa=$( cut -d, -f3 $timefile | tail -n +2 | paste -sd+ | bc -ql)
bisa=$( cut -d, -f5 $timefile | tail -n +2 | paste -sd+ | bc -ql)
isolationa=$( cut -d, -f7 $timefile | tail -n +2 | paste -sd+ | bc -ql)

echo "obo-all / isolation-all: $(echo "$oboa / $isolationa " | bc -ql)"
echo "bisection-all / isolation-all: $(echo "$bisa / $isolationa " | bc -ql)"

echo "obo-found / isolation-obo-found: $(echo "$obof / $isolationobof " | bc -ql)"
echo "bisection-found / isolation-bisection-found: $(echo "$bisf / $isolationbisf " | bc -ql)"

echo "obo-not-found / isolation-obo-not-found: $(echo "$obon / $isolationobon ")"
echo "bisection-not-found / isolation-bisection-not-found: $(echo "$bisn / $isolationbisn ")"


echo "obo-not-found / isolation-obo-not-found: $(echo "$obon / $isolationobon " | bc -ql)"
echo "bisection-not-found / isolation-bisection-not-found: $(echo "$bisn / $isolationbisn " | bc -ql)"

# # none of the configurations found
# obon=$( grep ",0,.*,0,.*,0$" $timefile | cut -d, -f3 | tail -n +2 | paste -sd+ | bc -ql)
# bisn=$( grep ",0,.*,0,.*,0$" $timefile | cut -d, -f5 | tail -n +2 | paste -sd+ | bc -ql)
# isolationn=$( grep ",0,.*,0,.*,0$" $timefile | cut -d, -f7 | tail -n +2 | paste -sd+ | bc -ql)

# # at least one configuration found
# obof=$( grep -v ",0,.*,0,.*,0$" $timefile | cut -d, -f3 | tail -n +2 | paste -sd+ | bc -ql)
# bisf=$( grep -v ",0,.*,0,.*,0$" $timefile | cut -d, -f5 | tail -n +2 | paste -sd+ | bc -ql)
# isolationf=$( grep -v ",0,.*,0,.*,0$" $timefile | cut -d, -f7 | tail -n +2 | paste -sd+ | bc -ql)
