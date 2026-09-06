#!/usr/bin/env python3
"""
niri-desktop — a minimal ~/Desktop overlay for niri/Wayland
Dependencies: gtk4, gtk4-layer-shell (with GObject introspection), python-gobject

  Arch:   sudo pacman -S gtk4 gtk4-layer-shell python-gobject
  NixOS:  gtk4-layer-shell, python3Packages.pygobject3
  Debian: sudo apt install gir1.2-gtk-4.0 libgtk4-layer-shell-dev python3-gi

Config file: ~/.config/niri-desktop/config.toml
  (created automatically with defaults on first run)
"""

import gi
import os
import subprocess
import sys
import tomllib
from pathlib import Path

gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gtk4LayerShell as GtkLayerShell, Gtk, Gio, GLib, Gdk, GObject, Pango

# ── XDG Config ───────────────────────────────────────────────────────────────

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "niri-desktop"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = """\
# niri-desktop configuration

[settings]
# Maximum number of icon columns
columns = 4
# Icon size in pixels
icon_size = 64
# Distance from screen edge in pixels
margin = 16
# Directory to watch and display
desktop_dir = "~/Desktop"

[projects]
# Add your projects here as name = "path"
# Examples:
# sequesto = "~/work/sequesto"
# nadir = "~/projects/nadir"
# voice-evo = "~/projects/voice-evo"

# [firstmate]
# Optional. Path to a capture script. When set and the script exists,
# the right-click menu shows a "Send to firstmate" action.
# inbox_script = "~/Code/Me/firstmate/bin/fm-inbox.sh"
"""

def ensure_config() -> dict:
    """Load config, creating default if missing. Returns parsed config dict."""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(DEFAULT_CONFIG)
        print(f"Created default config at {CONFIG_FILE}", file=sys.stderr)

    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def load_settings(config: dict) -> dict:
    s = config.get("settings", {})
    fm = config.get("firstmate", {})
    inbox_script = fm.get("inbox_script")
    return {
        "columns":     s.get("columns", 4),
        "icon_size":   s.get("icon_size", 64),
        "margin":      s.get("margin", 16),
        "desktop_dir": Path(s.get("desktop_dir", "~/Desktop")).expanduser(),
        "firstmate_inbox_script": Path(inbox_script).expanduser() if inbox_script else None,
    }


def load_projects(config: dict) -> list[tuple[str, Path]]:
    """Return list of (name, path) tuples from [projects] section."""
    projects = []
    for name, raw_path in config.get("projects", {}).items():
        path = Path(raw_path).expanduser()
        if path.exists():
            projects.append((name, path))
        else:
            print(f"Warning: project '{name}' path does not exist: {path}", file=sys.stderr)
    return projects


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_icon_for_file(path: Path, icon_size: int) -> Gtk.Image:
    try:
        gfile = Gio.File.new_for_path(str(path))
        info = gfile.query_info(
            "standard::icon,standard::content-type",
            Gio.FileQueryInfoFlags.NONE,
            None,
        )
        gicon = info.get_icon()
        if gicon:
            img = Gtk.Image.new_from_gicon(gicon)
            img.set_pixel_size(icon_size)
            return img
    except Exception:
        pass

    if path.is_dir():
        icon_name = "folder"
    elif path.suffix in (".py", ".js", ".ts", ".rs", ".c", ".cpp", ".go"):
        icon_name = "text-x-script"
    elif path.suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        icon_name = "image-x-generic"
    elif path.suffix in (".pdf",):
        icon_name = "application-pdf"
    elif path.suffix in (".zip", ".tar", ".gz", ".xz", ".bz2", ".zst"):
        icon_name = "package-x-generic"
    elif path.suffix in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
        icon_name = "video-x-generic"
    elif path.suffix in (".mp3", ".flac", ".ogg", ".wav"):
        icon_name = "audio-x-generic"
    else:
        icon_name = "text-x-generic"

    img = Gtk.Image.new_from_icon_name(icon_name)
    img.set_pixel_size(icon_size)
    return img


def open_file(path: Path):
    subprocess.Popen(["xdg-open", str(path)], env=os.environ)


def move_file_to(src: Path, dest_dir: Path):
    import shutil
    try:
        shutil.move(str(src), str(dest_dir / src.name))
    except Exception as e:
        print(f"Move failed: {e}", file=sys.stderr)


def delete_permanently(path: Path):
    import shutil
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    except Exception as e:
        print(f"Delete failed: {e}", file=sys.stderr)


# ── File item widget ──────────────────────────────────────────────────────────

class FileItem(Gtk.Box):
    def __init__(self, path: Path, settings: dict, projects: list, on_moved):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.path = path
        self.on_moved = on_moved
        self.projects = projects
        self.settings = settings

        cell_width = max(90, settings["icon_size"] + 26)
        cell_height = settings["icon_size"] + 36
        self.set_size_request(cell_width, cell_height)

        icon = get_icon_for_file(path, settings["icon_size"])
        icon.set_halign(Gtk.Align.CENTER)
        self.append(icon)

        label = Gtk.Label(label=path.name)
        label.set_max_width_chars(10)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_halign(Gtk.Align.CENTER)
        label.set_wrap(False)
        label.add_css_class("file-label")
        self.append(label)

        self.add_css_class("file-item")
        self.set_cursor(Gdk.Cursor.new_from_name("grab", None))

        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("released", self._on_click)
        self.add_controller(click)

        rclick = Gtk.GestureClick()
        rclick.set_button(3)
        rclick.connect("released", self._on_right_click)
        self.add_controller(rclick)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self.add_css_class("file-item-hover"))
        motion.connect("leave", lambda *_: self.remove_css_class("file-item-hover"))
        self.add_controller(motion)

        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self._on_drag_prepare)
        drag_source.connect("drag-begin", self._on_drag_begin)
        self.add_controller(drag_source)

    def _on_drag_prepare(self, source, x, y):
        gfile = Gio.File.new_for_path(str(self.path))

        # File-list provider: gives text/uri-list (file:// URI) and the portal
        # file-transfer types. Browsers need these to treat the drop as a file
        # upload, like a drag from a file manager.
        file_list = Gdk.FileList.new_from_list([gfile])
        flist_val = GObject.Value(Gdk.FileList)
        flist_val.set_boxed(file_list)
        provider_files = Gdk.ContentProvider.new_for_value(flist_val)

        # Plain-text path provider: keeps the path-paste behavior for terminals
        # such as Claude Code.
        provider_text = Gdk.ContentProvider.new_for_bytes(
            "text/plain;charset=utf-8",
            GLib.Bytes.new(str(self.path).encode()),
        )

        return Gdk.ContentProvider.new_union([provider_files, provider_text])

    def _on_drag_begin(self, source, drag):
        size = self.settings["icon_size"]
        icon_widget = get_icon_for_file(self.path, size)
        drag_icon = Gtk.DragIcon.get_for_drag(drag)
        drag_icon.set_child(icon_widget)
        drag.set_hotspot(size // 2, size // 2)

    def _on_click(self, gesture, n_press, x, y):
        open_file(self.path)

    def _on_right_click(self, gesture, n_press, x, y):
        menu = Gtk.Popover()
        menu.set_parent(self)
        menu.set_has_arrow(False)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vbox.set_margin_top(6)
        vbox.set_margin_bottom(6)
        vbox.set_margin_start(6)
        vbox.set_margin_end(6)

        open_btn = Gtk.Button(label="Open")
        open_btn.add_css_class("menu-item")
        open_btn.connect("clicked", lambda _: (open_file(self.path), menu.popdown()))
        vbox.append(open_btn)

        nvim_btn = Gtk.Button(label="Open in Neovim")
        nvim_btn.add_css_class("menu-item")
        nvim_btn.connect(
            "clicked",
            lambda _: (
                subprocess.Popen(
                    ["xdg-terminal-exec", "nvim", str(self.path)],
                    env=os.environ,
                ),
                menu.popdown(),
            ),
        )
        vbox.append(nvim_btn)

        if self.path.is_dir():
            term_btn = Gtk.Button(label="Open Terminal Here")
            term_btn.add_css_class("menu-item")
            term_btn.connect(
                "clicked",
                lambda _: (
                    subprocess.Popen(
                        ["xdg-terminal-exec"],
                        cwd=str(self.path),
                        env={**os.environ, "PWD": str(self.path)},
                    ),
                    menu.popdown(),
                ),
            )
            vbox.append(term_btn)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        vbox.append(sep)

        if self.projects:
            move_label = Gtk.Label(label="Move to project…")
            move_label.add_css_class("menu-section-label")
            move_label.set_halign(Gtk.Align.START)
            vbox.append(move_label)

            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_max_content_height(200)
            scroll.set_propagate_natural_height(True)

            proj_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for name, proj_path in self.projects:
                btn = Gtk.Button(label=name)
                btn.add_css_class("menu-item")
                btn.add_css_class("menu-item-project")
                btn.connect(
                    "clicked",
                    lambda _, p=proj_path: (
                        move_file_to(self.path, p),
                        menu.popdown(),
                        self.on_moved(),
                    ),
                )
                proj_box.append(btn)

            scroll.set_child(proj_box)
            vbox.append(scroll)
        else:
            no_proj = Gtk.Label(label=f"No projects in {CONFIG_FILE}")
            no_proj.add_css_class("menu-section-label")
            vbox.append(no_proj)

        inbox_script = self.settings.get("firstmate_inbox_script")
        if inbox_script and inbox_script.exists():
            fm_btn = Gtk.Button(label="Send to firstmate")
            fm_btn.add_css_class("menu-item")
            fm_btn.connect(
                "clicked",
                lambda _: (
                    subprocess.Popen(
                        [
                            str(inbox_script),
                            "note",
                            f"niri-desktop: please look at {self.path}",
                        ],
                        env=os.environ,
                    ),
                    menu.popdown(),
                ),
            )
            vbox.append(fm_btn)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(4)
        sep2.set_margin_bottom(4)
        vbox.append(sep2)

        trash_btn = Gtk.Button(label="Move to Trash")
        trash_btn.add_css_class("menu-item")
        trash_btn.add_css_class("menu-item-danger")
        trash_btn.connect(
            "clicked",
            lambda _: (
                Gio.File.new_for_path(str(self.path)).trash(None),
                menu.popdown(),
                self.on_moved(),
            ),
        )
        vbox.append(trash_btn)

        # Permanent delete. Two-step: first click reveals a confirm button.
        delete_btn = Gtk.Button(label="Delete")
        delete_btn.add_css_class("menu-item")
        delete_btn.add_css_class("menu-item-danger")
        vbox.append(delete_btn)

        confirm_btn = Gtk.Button(label="Confirm delete")
        confirm_btn.add_css_class("menu-item")
        confirm_btn.add_css_class("menu-item-danger")
        confirm_btn.set_visible(False)
        confirm_btn.connect(
            "clicked",
            lambda _: (
                delete_permanently(self.path),
                menu.popdown(),
                self.on_moved(),
            ),
        )
        vbox.append(confirm_btn)

        delete_btn.connect(
            "clicked",
            lambda _: (delete_btn.set_visible(False), confirm_btn.set_visible(True)),
        )

        menu.set_child(vbox)
        menu.popup()


# ── Main window ───────────────────────────────────────────────────────────────

class DesktopWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("niri-desktop")
        self.set_decorated(False)
        self.set_resizable(False)

        self._reload_config()

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BOTTOM)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, self.settings["margin"])
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, self.settings["margin"])
        GtkLayerShell.auto_exclusive_zone_enable(self)

        self.add_css_class("desktop-window")

        self.grid = Gtk.FlowBox()
        self.grid.set_max_children_per_line(self.settings["columns"])
        self.grid.set_min_children_per_line(1)
        self.grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.grid.set_row_spacing(8)
        self.grid.set_column_spacing(8)
        self.grid.set_homogeneous(True)
        self.grid.add_css_class("desktop-grid")

        self.set_child(self.grid)
        self.refresh()

        # Watch ~/Desktop
        gfile = Gio.File.new_for_path(str(self.settings["desktop_dir"]))
        self.dir_monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.dir_monitor.connect("changed", self._on_dir_changed)

        # Watch config file — live reload on save
        cfg_gfile = Gio.File.new_for_path(str(CONFIG_FILE))
        self.cfg_monitor = cfg_gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.cfg_monitor.connect("changed", self._on_config_changed)

    def _reload_config(self):
        config = ensure_config()
        self.settings = load_settings(config)
        self.projects = load_projects(config)

    def refresh(self):
        while True:
            child = self.grid.get_first_child()
            if child is None:
                break
            self.grid.remove(child)

        desktop = self.settings["desktop_dir"]
        if not desktop.exists():
            desktop.mkdir(parents=True, exist_ok=True)

        entries = sorted(
            [p for p in desktop.iterdir() if not p.name.startswith(".")],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )

        for path in entries:
            item = FileItem(path, self.settings, self.projects, on_moved=self.refresh)
            self.grid.append(item)

    def _on_dir_changed(self, monitor, file, other_file, event_type):
        GLib.timeout_add(200, self._delayed_refresh)

    def _delayed_refresh(self):
        self.refresh()
        return False

    def _on_config_changed(self, monitor, file, other_file, event_type):
        GLib.timeout_add(300, self._delayed_config_reload)

    def _delayed_config_reload(self):
        try:
            self._reload_config()
            self.grid.set_max_children_per_line(self.settings["columns"])
            self.refresh()
            print("Config reloaded.", file=sys.stderr)
        except Exception as e:
            print(f"Config reload failed (check TOML syntax): {e}", file=sys.stderr)
        return False


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = b"""
.desktop-window {
    background: transparent;
}

.desktop-grid {
    background: transparent;
    padding: 0;
}

.file-item {
    border-radius: 8px;
    padding: 6px 4px;
    transition: background 120ms ease;
}

.file-item-hover {
    background: rgba(255, 255, 255, 0.12);
}

.file-label {
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 11px;
    color: white;
    text-shadow: 0px 1px 3px rgba(0,0,0,0.9);
}

.menu-item {
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 13px;
    color: #e8e8e8;
}

.menu-item:hover {
    background: rgba(255,255,255,0.12);
}

.menu-item-project {
    font-size: 12px;
    color: #aad4ff;
    padding-left: 16px;
}

.menu-item-danger {
    color: #ff7070;
}

.menu-section-label {
    font-size: 11px;
    color: #888;
    padding: 2px 10px;
}

popover > contents {
    background: rgba(30, 30, 35, 0.92);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 4px 0;
}
"""


# ── App entry ─────────────────────────────────────────────────────────────────

class DesktopApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.jeffry.niri-desktop")

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        win = DesktopWindow(self)
        win.present()


if __name__ == "__main__":
    app = DesktopApp()
    sys.exit(app.run(sys.argv))
