import argparse
import main

parser = argparse.ArgumentParser()
parser.add_argument("-i", required=True)
parser.add_argument("-p", required=True, type=int)

args = parser.parse_args()

main.main(args.i, args.p)
