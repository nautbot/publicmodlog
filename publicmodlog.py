import subprocess, traceback

while True:
    try:
        p = subprocess.call(['python3', 'publicmodlogloop.py'])
    except (SyntaxError, FileNotFoundError):
        p = subprocess.call(['python', 'publicmodlogloop.py'])
    except:
        traceback.print_exc()
        pass