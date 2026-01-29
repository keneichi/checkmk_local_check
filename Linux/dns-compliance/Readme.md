# Usage
Ce check vérifie sur chaque machine la cohérence DNS entre l'IP, l'enregistrement PTR et le champ A.  
Il devient inutile (et redondant) si le lan-compliance est utilisé (les checks de conformités qui s'appuient sur ScanOpy)  

# script
Le script dns-compliance est à déposer dans /usr/lib/check_mk_agent/local/

# config file
Le fichier de configuration (checkmk_dns_compliance.conf) est à déposer dans /etc/

Adapter la configuration du fichier de configuration :

```bash 
enable=True/False
domain=domain.local
```
