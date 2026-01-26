# location
le check est à installer dans le dossier */usr/lib/check_mk_agent/local/60/*  

Le dossier 60 indique que le check se déroule toutes les 60 secondes (indispensable pour un vérifier la vie du VPN)

# configuration

Le fichier de conf donnant des noms au vpn est à mettre dans */etc/check_mk/local_check_conf/wireguard_peers.conf*  
Ainsi le check dans checkMK affichera WireGuard_wg0_peer_VPN_NAME plutot WireGuard_wg0_peer_PUBKEY


