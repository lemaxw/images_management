import subprocess
import sys

def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except subprocess.CalledProcessError:
        print(f"Could not install package: {package}")

def main():
    with open('requirements_py.txt') as f:
        packages = f.read().splitlines()

    for package in packages:
        install(package)

if __name__ == "__main__":
    main()
