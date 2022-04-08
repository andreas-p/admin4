#! /bin/bash
#
# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License,
# see LICENSE.TXT for conditions of usage

if [ -z "$(xhost | grep LOCAL:)" ] ; then
  # allow local access
  xhost local:root
fi

image=${1-adminfour/admin4:latest}
IFS=":" read user _pwd uid gid _name home _shell  <<< $(grep ^$(whoami): /etc/passwd)

docker run -ti --rm --name admin4 \
	--net=host --env=DISPLAY=unix$DISPLAY \
	--volume /tmp/.X11-unix:/tmp/.X11-unix \
	--volume /etc/passwd:/etc/passwd \
        --volume $home:$home \
	--user $uid:$gid \
	$image

