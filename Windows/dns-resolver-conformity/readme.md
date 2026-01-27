# Contexte
Ce script vise à s'assurer que les serveurs DNS d'une machine Windows sont correctement définis et conformes à une configuration de référence.

# Usage

* Placer le fichier de configuration (**resolver_dns.conf**) dans le dossier  
  **C:\ProgramData\checkmk\agent\config\\** (le créer si nécessaire)
* Placer le local check (**dns_resolver_conformity.ps1**) dans  
  **C:\ProgramData\checkmk\agent\local\\**

⚠️ **Penser à adapter la configuration en fonction du réseau**

⚠️ **Note importante : le fichier de configuration exclut volontairement la plupart des interfaces virtuelles**
(VPN, Hyper-V, VirtualBox, WSL, etc.), afin d’éviter les faux positifs.

# Résultats / Règles de conformité

Le check applique les règles suivantes :

* Vérifie que les serveurs DNS configurés sur les interfaces réseau actives sont conformes à la configuration de référence.
* **WARNING** si un ou plusieurs serveurs DNS non autorisés sont définis.
* **CRITICAL** si aucun des serveurs DNS définis dans le fichier de configuration n’est présent.
* **CRITICAL** si le serveur DNS primaire d’une interface n’est pas présent dans le fichier de configuration.
* Si un serveur DNS configuré correspond à **localhost** (127.0.0.1 ou ::1), le check vérifie qu’un service DNS est bien actif localement :
  * **OK** si un serveur DNS local est détecté.
  * **CRITICAL** dans le cas contraire.
