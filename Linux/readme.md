# Généralités
Sauf mention contraire, tous les check locaux sont à installer dans le dossier **/usr/lib/check_mk_agent/local/**

## dns-compliance
Checks pour vérifier la conformité de chaque host à un record DNS.  
* Un check vérifie la coinfirmité entre l'IP et le champ A  
* L'autre en le champs PTR et l'IP  
* Un troisième vérifie la conformité entre le hostname et l'enregitrement DNS A

## check_docker_updates.sh
Ce check Vérifie la disponibilité d'une mise à jour du (ou des) logiciel(s) fonctionnant en docker (containers)  

## check_updates.py
Ce check Vérifie la disponibilité de mise à jour du système.  
Trois checks sont créés :  
* Updates_Normal = Warning si des mises à jour dispo 
* Updates_Security = Critical si des mises à jour dispo
* Updates_Reboot = Critical si le système a besoin d'un redémarrage

## checkos.py
Ce check vérifie que la version de l'OS est bien la dernière disponible.

## git_checks.sh
Ce check vérifie que le dépot local soit bien synchronisé avec le déport github.  
Aussi bien en download (github plus récent que le repertoire local) qu'en upload ((répertoire local avec des modifications non reportées sur le depot github)

## check_checkmk_updates.py
Ce check vérifie la disponibilité d'une nouvelle version de CheckMK server

## nextcloud_version.sh
Ce Check vérifie la présence de mises à jour pour Nextcloud mais aussi pour les applications utilisées sur l'instance Nextcloud

## pbs-datastore
Ce check vérifie, lors de l'utilisation conjointe d'un serveurs Proxmox VE et Proxmox BS, que le datastore de backup est bien connecté sur le serveur PVE.
Penser à ajuster la variable DATASTORE en début de fichier pour inscire le nom de votre datastore
