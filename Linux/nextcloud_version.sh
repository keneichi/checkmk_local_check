#!/bin/bash

output=$(sudo -u www-data php /var/www/nextcloud/occ update:check 2>/dev/null)

# --- CORE ---
core_line=$(echo "$output" | grep -E '^Nextcloud [0-9]+\.[0-9]+\.[0-9]+ is available')
if [[ -n "$core_line" ]]; then
    version=$(echo "$core_line" | awk '{print $2}')
    echo "2 nextcloud_core_update - MISE À JOUR Nextcloud dispo : $version"
else
    echo "0 nextcloud_core_update - Nextcloud core à jour"
fi

# --- APPS ---
apps_lines=$(echo "$output" | grep -E '^Update for')
if [[ -n "$apps_lines" ]]; then
    app_list=$(echo "$apps_lines" \
        | sed -E 's/^Update for ([^ ]+) to version.*/\1/' \
        | tr '\n' ',' | sed 's/,$//')
    nb_apps=$(echo "$apps_lines" | wc -l | tr -d ' ')
    echo "1 nextcloud_apps_update - $nb_apps application(s) à mettre à jour : $app_list"
else
    echo "0 nextcloud_apps_update - Apps à jour"
fi
