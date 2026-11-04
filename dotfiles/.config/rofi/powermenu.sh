#!/bin/bash

case "$1" in
    "Выключить")
        systemctl poweroff
        ;;
    "Перезагрузить")
        systemctl reboot
        ;;
    "Выйти")
        openbox --exit
        ;;
esac

if [ -z "$1" ]; then
    printf '%s\n' "Выключить" "Перезагрузить" "Выйти"
fi
