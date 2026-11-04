# Sources and ownership

- `vendor/i3lock` is the exact locally modified i3lock 2.15 source, including the custom input indicator. Upstream: https://github.com/i3/i3lock. Its original license is retained in `vendor/i3lock/LICENSE`; this repository does not relicense it.
- Openbox themes include local Laptos-Switcher and a Catppuccin Mocha theme present in the snapshot. Upstream Catppuccin/Openbox: https://github.com/catppuccin/openbox. Retain original notices in the files; local alterations are part of this snapshot.
- GTK/Qt/Telegram visual styles and Python/shell integrations are copied from this user's existing configuration, with portability changes documented separately. No blanket license is assigned to the user's unpublished custom code by this export.
- Papirus, Adwaita, DejaVu, Noto and Hack are dependencies provided by their distribution packages. Their system font/icon files are not vendored wholesale.
- PanelNetworkIcons.ttf is a locally generated font. Its source generator, including Papirus-derived network glyph paths, is included under dotfiles/.config/polybar/assets. Papirus: https://github.com/PapirusDevelopmentTeam/papirus-icon-theme.
- The bundled cat artwork, lock logo and app-specific icons are existing visual assets from the user's configuration. They retain their respective owners' rights; source/redistribution licenses for individual image assets were not established by this export. They are not declared public domain or relicensed.
- No passwords, Telegram sessions, VPN subscriptions, browser profiles, private keys or application databases belong to this snapshot.
