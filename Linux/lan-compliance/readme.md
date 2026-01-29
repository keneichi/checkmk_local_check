# LAN COMPLIANCE - CheckMK / ScanOpy

## Contexte
Ce projet vise à vérifier la concordance d'un ou plusieurs réseaux à des normes définies.  

Il se constitue de plusieurs niveaux de conformités :
* Surveillance des équipements présents sur le réseaux 
* Conformité des enregistrements DNS

Ce projet s’appuie sur **Scanopy**  pour analyser un ou plusieurs réseaux et sur **checkmk** popur effectuer
les vérifications de conformités.

---

## Prérequis

- Une instance **Scanopy** (installée en Docker)
- Un **token API Scanopy**
- Un compte utilisateur dédié dans **Checkmk** (API / automation user)

---

## Variables d’environnement (commun à tous les checks)

Fichier de configuration contenant les paramètres et secrets (tokens API).

Chemin :
*/etc/check_mk/local_check_conf/lan-compliance.env*

Permissions recommandées :
```
chmod 600 /etc/check_mk/local_check_conf/lan-compliance.env
```

Ce fichier doit être adapté avec les informations propres à l’environnement  (URL, tokens, seuils, etc.).

---

## LAN DISCOVERY

### Emplacement et droits des fichiers

#### Script principal ("binaire")

Script Python réalisant la comparaison entre Scanopy et Checkmk.

Chemin :
*/usr/local/lib/lan-discovery.py*
```
chmod 755 /usr/local/lib/lan-discovery.py
```

#### Wrapper Checkmk (local check)

Script appelé par l’agent Checkmk.
Il charge les variables d’environnement puis exécute le script principal.

Chemin :
*/usr/lib/check_mk_agent/local/lan-discovery.sh*
```
chmod +x /usr/lib/check_mk_agent/local/lan-discovery.sh
```

### Fonctionnement

1. Le script récupère la liste des hôtes monitorés dans Checkmk.
2. Un différentiel est effectué entre Scanopy et Checkmk.
3. Les hôtes tagués nocheckmk dans Scanopy sont ignorés.
4. Une alerte Checkmk est générée si des hôtes non supervisés sont détectés.

### Résultat dans Checkmk

Le check apparaît sous la forme d’un service :

**LAN Discovery**

* OK : aucun hôte Scanopy non supervisé
* WARN / CRIT : un ou plusieurs hôtes découverts par Scanopy ne sont pas présents dans Checkmk


## DNS CONFORMITY
### Politique DNS appliquée

- Les enregistrements PTR sont considérés comme critiques.
  Une IP sans PTR ou avec plusieurs PTR est une non-conformité majeure.
- Les enregistrements A sont considérés comme une cohérence fonctionnelle.
  Une incohérence A/PTR génère un warning mais n’empêche pas le fonctionnement.
  
### Emplacement et droits 

Script appelé par l’agent Checkmk.
Il charge les variables d’environnement puis exécute le script principal.

Chemin :
*/usr/lib/check_mk_agent/local/dns_conformity.py*
```
chmod +x /usr/lib/check_mk_agent/local/dns_conformity.py
```

### Fonctionnement

1. Le script récupère la liste des hôtes découverts par ScanOpy.
2. Les adresses IP sont filtrées selon le périmètre défini (CIDR, tags).
3. Des vérifications DNS sont effectuées (PTR et A).

### Résultat dans Checkmk

Le check apparaît sous la forme d’un service :

**DNS_A_CONFORMITY**
* OK : aucun hôte Scanopy non supervisé
* WARN : PTR OK, mais pas de A / Plusieurs A pour une IP (suggestion d'utiliser CNAME) / incohérence entre PTR, A et IP

**DNS_PTR_CONFORMITY**
* OK : Tous les hôtes découverts par scanopy ont des enregistrements PTR correctement configuré
* CRIT : Pas d'enregistrement PTR trouvé / plusieurs PTR associés à une même IP

## Notes

Les changements de tags Scanopy sont pris en compte dynamiquement lors de
l’exécution des check.

Ce check est conçu pour fonctionner sans agent sur les équipements découverts.
