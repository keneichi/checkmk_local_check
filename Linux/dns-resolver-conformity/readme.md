# Contexte
Ce script vise à s'assurer que les serveurs DNS d'une machine sont correctement définis et conformes à une configuration de référence.

# Usage

* Placer le fichier de configuration (**resolver_dns.conf**) dans le dossier  
  **/etc/check_mk/local_check_conf/** (le créer si nécessaire)
* Placer le local check (**dns_resolver_conformity.py**) dans  
  **/usr/lib/check_mk_agent/local/**

⚠️ **Penser à adapter la configuration en fonction du réseau**

# Résultats / Règles de conformité

Le check applique les règles suivantes :

* Vérifie que le fichier **resolv.conf** ne contient que des serveurs DNS autorisés.
* **WARNING** si un ou plusieurs serveurs DNS non autorisés sont définis.
* **CRITICAL** si aucun des serveurs DNS définis dans le fichier de configuration n’est présent.
* **CRITICAL** si le premier serveur DNS configuré n’est pas présent dans le fichier de configuration.
* Si **resolv.conf** pointe vers **127.0.0.1** (ou plus généralement *localhost*), le check vérifie qu’un service DNS est bien actif localement :
  * **OK** si un serveur DNS local est détecté.
  * **CRITICAL** dans le cas contraire.
