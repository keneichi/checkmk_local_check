# dns-compliance
Checks pour vérifier la conformité de chaque host à un record DNS.  
Un check vérifie la coinfirmité entre l'IP et le champ A  
L'autre en le champs PTR et l'IP  

# check_docker_updates.sh
Ce check Vérifie la disponibilité d'une mise à jour du (ou des) logiciel(s) fonctionnant en docker  

# check_updates.py
Ce check Vérifie la disponibilité de mise à jour du système.  
Trois checks sont créés :  
* Updates_Normal = Warning si des mises à jour dispo 
* Updates_Security = Critical si des mises à jour dispo
* Updates_Reboot = Critical si le système a besoin d'un redémarrage

# checkos.py
Ce check vérifie que la version de l'OS est bien la dernière disponible.
