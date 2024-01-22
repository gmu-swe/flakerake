yes | sudo apt install gcc

mkdir -p protoc
cd protoc
wget https://github.com/google/protobuf/releases/download/v2.5.0/protobuf-2.5.0.tar.gz
tar -xzvf protobuf-2.5.0.tar.gz
rm protobuf-2.5.0.tar.gz
cd protobuf-2.5.0
./autogen.sh
./configure --prefix=/usr
make
sudo make install
protoc --version

cd java
mvn install -DskipTests
