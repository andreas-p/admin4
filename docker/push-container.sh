#! /bin/bash
tag=${1-$(git tag | tail -1)}
docker push adminfour/admin4:$tag
docker push adminfour/admin4:latest
