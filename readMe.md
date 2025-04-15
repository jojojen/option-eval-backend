python3 -m venv --without-pip
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
conda deactivate
conda activate
python get-pip.py
pip --version
python app.py