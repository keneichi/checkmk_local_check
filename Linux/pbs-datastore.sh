#!/bin/bash

DATASTORE="backup"
CMD_OUTPUT=$(pvesm status --storage "$DATASTORE" 2>&1)
RC=$?

# Erreur de commande (pbs inaccessible, cert cassé, etc.)
if [ $RC -ne 0 ]; then
  echo "2 pbs_datastore - Erreur pvesm: $CMD_OUTPUT"
  exit 0
fi

STATUS=$(echo "$CMD_OUTPUT" | awk 'NR==2 {print $3}')

if [ "$STATUS" = "active" ]; then
  echo "0 pbs_datastore - Datastore PBS '$DATASTORE' actif"
else
  echo "2 pbs_datastore - Datastore PBS '$DATASTORE' NON actif (status=$STATUS)"
fi
