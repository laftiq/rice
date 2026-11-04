# Отдельные приложения и входы

## Firefox

После установки открой about:profiles и скопируй корневую папку нужного профиля. Закрой Firefox. Предпросмотр и применение:

```bash
python3 ~/.config/rice/firefox/apply.py --profile /путь/к/профилю
python3 ~/.config/rice/firefox/apply.py --profile /путь/к/профилю --apply
```

Сохраняются резервные user.js и chrome CSS в ~/.local/state/laptos-rice/firefox/. Cookies, пароли, расширения, закладки и другие настройки профиля не импортируются.

## Telegram / Аюграм

Установи клиент самостоятельно. Обёртка telegram-desktop ожидает /usr/bin/telegram-desktop, задаёт GTK3/Fusion и Laptos-Rice для диалогов. Для другой поставки (Flatpak/AppImage) адаптируй launcher под её команду. Цветовые файлы в ~/.config/rice/telegram/*/colors.tdesktop-theme и ~/.config/rice/ayugram/colors.tdesktop-theme открываются/применяются внутри Telegram-клиента; tdata не нужна для самого райса. Выбранную тему потребуется подтвердить в новом клиенте.

## Яндекс Музыка

Официальная загрузка: https://music.yandex.ru/download/. Сохранён desktop launcher для исходного пути /opt/Яндекс Музыка/yandexmusic и иконка. При другой поставке поменяй Exec. Панель читает MPRIS, поэтому другие совместимые плееры тоже обнаруживаются. Проверка: playerctl --list-all.

## Happ

Установи приложение из официального источника: https://www.happ.su/. Интеграция исходного райса ожидает /opt/happ/bin/Happ и его StatusNotifier/DBusMenu. Она сохраняет свои меню и команды, но не устанавливает VPN-подписки, TUN-правила, права администратора и не импортирует профиль. При другой версии меню клиента может отличаться.

## Pano Scrobbler / Last.fm

Источник: https://kawaiidango.github.io/. Сохранён XDG autostart запуска в свёрнутом виде; клиент и вход в Last.fm добавляются отдельно. Секреты Last.fm и внутренние базы приложения не нужны для оформления и не экспортируются.

## Обычные приложения

Установщик ставит ksnip, файловый менеджер и архиватор из Debian. Браузер и повседневные программы можно выбрать отдельно: в исходной сессии используется firefox-esr. Выбор браузера не требуется для запуска Openbox. Обёртки предпочитают ~/.local/bin через PATH сессии.
