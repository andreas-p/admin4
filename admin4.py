#!/usr/bin/env python3
# The Admin4 Project
# (c) 2013-2025 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

if __name__ == "__main__":
  import sys, os

  loaddir=os.path.dirname(os.path.abspath(sys.argv[0]))
  sys.path.insert(0, loaddir)
  from main import main
  main(sys.argv)
