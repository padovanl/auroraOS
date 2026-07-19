# Headless development environment for the Aurora desktop: runs labwc with
# the headless wlroots backend so the shell can be exercised and screenshotted.
FROM debian:trixie

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        labwc grim wlr-randr foot dbus dbus-user-session \
        python3 python3-gi python3-gi-cairo python3-cairo python3-numpy python3-pywayland python3-cffi-backend libwayland-dev pkgconf \
        gir1.2-gtk-4.0 gir1.2-adw-1 libgtk4-layer-shell0 gir1.2-gtk4layershell-1.0 \
        gir1.2-nm-1.0 gir1.2-upowerglib-1.0 gir1.2-polkit-1.0 gir1.2-gnomedesktop-4.0 \
        gsettings-desktop-schemas dconf-gsettings-backend libglib2.0-bin \
        adwaita-icon-theme papirus-icon-theme librsvg2-common \
        fonts-inter fonts-noto-core fonts-noto-color-emoji \
        gnome-calculator gnome-text-editor mousepad libnotify-bin \
        gettext make rsync locales wlrctl \
        python3-pytest python3-yaml desktop-file-utils libxml2-utils shellcheck \
    && sed -i 's/^# *\(en_US.UTF-8\|it_IT.UTF-8\)/\1/' /etc/locale.gen && locale-gen \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8
