# Contexte
Ce check s'installe sur le serveur Proxmox Backup Server
Il nécessite l'installation du paquet proxmox-backup-client sur la machine à backuper

# Installation du paquet proxmox-backup-client sur la machine à sauvegarder

## On ajoute les sources pour le dépot proxmox
### On ajoute le fichier de signature du dépot
```
wget https://enterprise.proxmox.com/debian/proxmox-release-trixie.gpg -O /usr/share/keyrings/proxmox-archive-keyring.gpg
```
### On ajoute le fichiers de repo proxmox

*/etc/apt/sources.list.d/proxmox.sources*
```Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: trixie
Components: pve-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
```
### on ajoute un fichier pour que seul le paquet proxmox-backup-client soit le seul à être mis à jour
*/etc/apt/preferences.d/proxmox-backup*
```
Package: proxmox-backup-client
Pin: origin "download.proxmox.com"
Pin-Priority: 1001

Package: *
Pin: origin "download.proxmox.com"
Pin-Priority: -1
```
## puis on installe le paquet
```
apt install proxmox-backup-client
```

# Sur la machine Proxmox Backup Server

On colle le script dans */usr/local/lib/pbs_snapshot_age.py*

On colle le wrapper dans */usr/lib/check_mk_agent/local/pbs_backup.sh*
