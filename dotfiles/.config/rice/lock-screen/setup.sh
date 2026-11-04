#!/bin/sh
set -eu
root="$HOME/.config/rice/lock-screen"
if [ ! -s "$root/logo.png" ]; then
    /usr/bin/python3 "$root/fetch-logo.py"
fi
if ! command -v i3lock >/dev/null || ! command -v xss-lock >/dev/null; then
    sudo apt-get install -y i3lock xss-lock
fi
/usr/bin/python3 "$root/render.py"
test -r /etc/pam.d/i3lock
touch "$root/ready"
"$HOME/.config/rice/start-locker.sh"
echo 'Новая блокировка готова. Super+L — блокировка. Пароль пользователя + Enter — разблокировка.'
