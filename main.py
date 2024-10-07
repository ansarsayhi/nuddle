import subprocess
import sys


if __name__ == "__main__":
    subprocess.run([sys.executable, 'setup.py', 'build_ext', '--inplace'])
    subprocess.run([sys.executable, 'scraper.py'])
    subprocess.run(['streamlit', 'run', 'interface.py'])

