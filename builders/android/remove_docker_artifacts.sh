#!/bin/bash
docker rm `docker ps -aq`
docker rmi `docker images -aq`
docker buildx prune -f