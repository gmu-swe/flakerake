cwd=$(pwd)
# Install requirements
sudo apt-get install -y build-essential \
checkinstall \
libreadline-gplv2-dev \
libncursesw5-dev \
libssl-dev \
libsqlite3-dev \
tk-dev \
libgdbm-dev \
libc6-dev \
libbz2-dev \
zlib1g-dev \
openssl \
libffi-dev \
python3-dev \
python3-setuptools \
wget

# Prepare to build
mkdir -p /tmp/Python39
cd /tmp/Python39

wget https://www.python.org/ftp/python/3.9.1/Python-3.9.1.tar.xz
tar xvf Python-3.9.1.tar.xz
cd /tmp/Python39/Python-3.9.1
./configure
sudo make altinstall

yes | python3.9 -m pip install boto3

cd cwd

echo 'export PYTHON_FLAKY_BIN="$(which python3.9)"' >> $HOME/.profile
