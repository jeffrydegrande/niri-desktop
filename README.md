# niri-desktop

A minimal `~/Desktop` overlay for the [niri](https://github.com/YaLTeR/niri) Wayland compositor.

niri has no desktop layer of its own. `niri-desktop` draws your `~/Desktop`
files as an icon grid on the background, using GTK4 and `gtk4-layer-shell`.

## Features

- Shows each `~/Desktop` entry as an icon and label. Folders come first.
- Picks icons by file content type, then by extension.
- Left-click opens a file with `xdg-open`.
- Right-click menu:
  - Open
  - Open in Neovim (opens a terminal with `nvim` on the path)
  - Open Terminal Here (folders only)
  - Move to project (any path in your `[projects]` config)
  - Send to firstmate (only when the optional firstmate integration is set)
  - Move to Trash
  - Delete (permanent; needs a second click to confirm)
- Drag a file to a browser upload field or into a terminal. The drag carries
  both a `file://` URI and the plain text path.
- Live reload. It watches the desktop folder and the config file and refreshes
  on change.

## Dependencies

- GTK4
- `gtk4-layer-shell` (with GObject introspection)
- `python-gobject`

Install on Arch:

```sh
sudo pacman -S gtk4 gtk4-layer-shell python-gobject
```

NixOS: `gtk4-layer-shell`, `python3Packages.pygobject3`.
Debian: `sudo apt install gir1.2-gtk-4.0 libgtk4-layer-shell-dev python3-gi`.

## Install

```sh
./install.sh
```

This copies the launcher and the app to `~/.local/bin`, installs a user
systemd service, and starts it. The service is bound to `niri.service`.

Logs:

```sh
journalctl --user -u niri-desktop.service -f
```

## Configuration

The config file is `~/.config/niri-desktop/config.toml`. It is created with
defaults on first run.

```toml
[settings]
columns = 4          # maximum icon columns
icon_size = 64       # icon size in pixels
margin = 16          # distance from the screen edge in pixels
desktop_dir = "~/Desktop"

[projects]
# name = "path"; these appear in the right-click "Move to project" menu
# sequesto = "~/work/sequesto"

# Optional firstmate integration.
# [firstmate]
# inbox_script = "~/Code/Me/firstmate/bin/fm-inbox.sh"
```

Edits apply live. The app reloads the config on save.

### Firstmate integration (optional)

`firstmate` is a private capture tool. It is not needed to run niri-desktop.
Set `inbox_script` in a `[firstmate]` section to a capture script. When the
value is set and the script exists, the right-click menu shows a "Send to
firstmate" action. The action runs `inbox_script note "niri-desktop: please
look at <path>"` in the background. It does not block the app. If you do not
set this option, the action does not appear.

## License

MIT. See [LICENSE](LICENSE).
