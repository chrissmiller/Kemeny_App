echo "Building virtual environment..."
python3 -m venv Kemeny_Demo_Env
echo "Sourcing..."
source Kemeny_Demo_Env/bin/activate
echo "Installing packages..."
pip install -q --upgrade pip
pip install -q -I Cython==0.28.2
pip install -q kivy==1.10.1
pip install -q typing
echo "Ready to go!"
