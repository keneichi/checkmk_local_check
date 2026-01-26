# Scanopy – Shadow IT Checkmk

## Contexte

Ce check s’appuie sur **Scanopy** pour analyser un ou plusieurs réseaux et effectuer
un différentiel entre les hôtes découverts sur le réseau et les hôtes effectivement
monitorés dans **Checkmk**.

Lorsqu’un hôte est visible via Scanopy mais absent de Checkmk, une alerte est générée.

Il est possible d’appliquer un tag Scanopy **`nocheckmk`** sur un hôte découvert afin
d’indiquer qu’il est normal qu’il ne soit pas supervisé dans Checkmk (exception
fonctionnelle).

---

## Prérequis

- Une instance **Scanopy** (installée en Docker)
- Un **token API Scanopy**
- Un compte utilisateur dédié dans **Checkmk** (API / automation user)

---

## Emplacement et droits des fichiers

### Variables d’environnement

Fichier de configuration contenant les paramètres et secrets (tokens API).

Chemin :
*/etc/check_mk/local_check_conf/scanopy_shadowit.env*

Permissions recommandées :
```
chmod 600 /etc/check_mk/local_check_conf/scanopy_shadowit.env
```

Ce fichier doit être adapté avec les informations propres à l’environnement  (URL, tokens, seuils, etc.).

### Script principal ("binaire")

Script Python réalisant la comparaison entre Scanopy et Checkmk.

Chemin :
*/usr/local/lib/scanopy_shadowit.py*
```
chmod 755 /usr/local/lib/scanopy_shadowit.py
```

### Wrapper Checkmk (local check)

Script appelé par l’agent Checkmk.
Il charge les variables d’environnement puis exécute le script principal.

Chemin :
*/usr/lib/check_mk_agent/local/scanopy_shadowit*
```
chmod +x /usr/lib/check_mk_agent/local/scanopy_shadowit
```

## Fonctionnement

1. Scanopy découvre les hôtes présents sur le réseau.
2. Le script récupère la liste des hôtes monitorés dans Checkmk.
3. Un différentiel est effectué entre Scanopy et Checkmk.
4. Les hôtes tagués nocheckmk dans Scanopy sont ignorés.
5. Une alerte Checkmk est générée si des hôtes non supervisés sont détectés.

## Résultat dans Checkmk

Le check apparaît sous la forme d’un service :

**Scanopy Shadow IT**

* OK : aucun hôte Scanopy non supervisé
* WARN / CRIT : un ou plusieurs hôtes découverts par Scanopy ne sont pas présents dans Checkmk

## Notes

Les changements de tags Scanopy sont pris en compte dynamiquement lors de
l’exécution du check.

Ce check est conçu pour fonctionner sans agent sur les équipements découverts.
