#!/bin/bash

NEED_UPDATE=()
CONTAINERS=$(docker ps --format '{{.ID}}')

for CONTAINER in $CONTAINERS; do
    IMAGE=$(docker inspect --format='{{.Config.Image}}' "$CONTAINER")
    OLD_ID=$(docker inspect --format='{{.Image}}' "$CONTAINER")
    docker pull "$IMAGE" > /dev/null 2>&1
    NEW_ID=$(docker image inspect --format='{{.Id}}' "$IMAGE" 2>/dev/null)

    if [[ "$OLD_ID" != "$NEW_ID" ]]; then
        NEED_UPDATE+=("$IMAGE")
    fi
done

if [ ${#NEED_UPDATE[@]} -eq 0 ]; then
    echo "0 DockerUpdates - OK - Toutes les images sont à jour"
else
    echo "1 DockerUpdates - WARNING - MAJ dispo pour : ${NEED_UPDATE[*]}"
fi
