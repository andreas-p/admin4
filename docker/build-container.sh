#! /bin/bash

# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License,
# see LICENSE.TXT for conditions of usage

LAST=$(git tag |tail -1)
version=${1-$LAST}
repo=adminfour/admin4

docker build -t $repo:$version --build-arg VERSION=$version .
