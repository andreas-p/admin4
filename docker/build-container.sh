#! /bin/bash

# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License,
# see LICENSE.TXT for conditions of usage

LASTTAG=$(git tag |tail -1)
tag=${1-latest}
version=${2-$LASTTAG}
repo=adminfour/admin4

docker build -t $repo:$tag --build-arg VERSION=$version .
