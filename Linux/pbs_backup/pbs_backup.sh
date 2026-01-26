# ceci est un wrapper faisant appel au script /usr/local/lib/pbs_snapshot_age.py
# Les variables définisssent les options pour vérifier si les backups sont OK ou non
# --datastore = Nom du Datastore défini sur le serveur de Backup 
# type = défini le type debackup 
# id = nom de la machine à backuper
# service = nom du service qui apparait dans CheckMK
# warn-days  = Age a partir duquel le backup est défini comme étant trop vieux (alerte)
# crit-days = Age a partir duquel le backup est défini comme étant beaucoup trop vieux (critique)

#!/bin/bash
/usr/bin/python3 /usr/local/lib/pbs_snapshot_age.py \
  --datastore backup \
  --type host \
  --id srvmedia \
  --service "PBS Musique - âge du dernier backup" \
  --warn-days 8 \
  --crit-days 14
