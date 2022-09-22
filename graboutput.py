import os,sys,subprocess

def main():
    piped = sys.argv[2]
    cp = subprocess.run(piped,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    output = cp.stdout.decode('utf-8')
    subprocess.run(sys.argv[1].split(" ") + [output])

if __name__ == '__main__':
    main()
