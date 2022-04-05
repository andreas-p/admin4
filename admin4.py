#!/usr/bin/python3
# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

if __name__ == "__main__":
  import sys, os

  loaddir=os.path.dirname(os.path.abspath(sys.argv[0]))
  sys.path.insert(0, loaddir)

  main=__import__('main')
  main.main(sys.argv)
