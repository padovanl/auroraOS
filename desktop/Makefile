# Installs the Aurora desktop. Usage: make install DESTDIR=/path/to/rootfs PREFIX=/usr

PREFIX  ?= /usr
DESTDIR ?=
PYTHON  ?= python3

LIBDIR   := $(DESTDIR)$(PREFIX)/lib/aurora
BINDIR   := $(DESTDIR)$(PREFIX)/bin
SHAREDIR := $(DESTDIR)$(PREFIX)/share
DATADIR  := $(SHAREDIR)/aurora
WAYLAND_XML ?= /usr/share/wayland/wayland.xml

BRANDING := ../branding
# The dynamic wallpaper series the login screen and new accounts start with.
DEFAULT_SERIES := starfall

.PHONY: all install protocols translations wallpapers sounds pot check

all:

install: protocols translations wallpapers sounds
	install -d $(LIBDIR) $(BINDIR) $(DATADIR)
	rsync -a --delete --exclude __pycache__ aurora/ $(LIBDIR)/aurora/
	cp -r build/protocols $(LIBDIR)/aurora/protocols
	install -m 755 $$(find bin -maxdepth 1 -type f) $(BINDIR)/
	install -d $(DESTDIR)$(PREFIX)/libexec
	install -m 755 $$(find libexec -maxdepth 1 -type f) $(DESTDIR)$(PREFIX)/libexec/
	install -d $(DATADIR)/labwc $(DATADIR)/greeter $(DATADIR)/wayfire $(DATADIR)/style $(DATADIR)/gtk
	install -m 644 data/gtk/* $(DATADIR)/gtk/
	install -m 644 data/labwc/* $(DATADIR)/labwc/
	install -m 644 data/wayfire/* $(DATADIR)/wayfire/
	install -m 644 data/greeter/* $(DATADIR)/greeter/
	install -m 644 data/style/* $(DATADIR)/style/
	install -d $(SHAREDIR)/themes
	$(PYTHON) data/themes/generate.py $(SHAREDIR)/themes
	install -d $(SHAREDIR)/icons
	$(PYTHON) $(BRANDING)/icons/generate.py $(SHAREDIR)/icons
	install -d $(SHAREDIR)/wayland-sessions $(SHAREDIR)/applications
	install -m 644 data/wayland-sessions/*.desktop $(SHAREDIR)/wayland-sessions/
	# With every language's name and description (Name[it]=File…).
	for f in data/applications/*.desktop; do \
		msgfmt --desktop --template=$$f -d po -o $(SHAREDIR)/applications/$$(basename $$f) || exit 1; \
	done
	install -d $(SHAREDIR)/xdg-desktop-portal
	install -m 644 data/portals/*.conf $(SHAREDIR)/xdg-desktop-portal/
	install -d $(SHAREDIR)/glib-2.0/schemas
	install -m 644 data/schemas/* $(SHAREDIR)/glib-2.0/schemas/
	install -d $(SHAREDIR)/icons/hicolor/scalable/apps $(SHAREDIR)/icons/hicolor/symbolic/apps
	install -m 644 data/icons/scalable/apps/* $(SHAREDIR)/icons/hicolor/scalable/apps/
	install -m 644 data/icons/symbolic/apps/* $(SHAREDIR)/icons/hicolor/symbolic/apps/
	install -d $(SHAREDIR)/backgrounds/aurora
	install -m 644 build/wallpapers/*.png $(SHAREDIR)/backgrounds/aurora/
	for phase in dawn day dusk night; do \
		ln -sf aurora-$(DEFAULT_SERIES)-$$phase.png \
			$(SHAREDIR)/backgrounds/aurora/aurora-dynamic-$$phase.png; \
	done
	install -d $(SHAREDIR)/sounds/aurora
	install -m 644 build/sounds/*.wav $(SHAREDIR)/sounds/aurora/
	cp -r build/locale/. $(SHAREDIR)/locale/

# Python bindings for Wayland protocols the shell speaks directly.
protocols:
	rm -rf build/protocols && mkdir -p build/protocols
	$(PYTHON) -m pywayland.scanner -i $(WAYLAND_XML) protocols/*.xml -o build/protocols
	touch build/protocols/__init__.py

translations:
	rm -rf build/locale
	for po in po/*.po; do \
		[ -e "$$po" ] || continue; \
		lang=$$(basename $$po .po); \
		mkdir -p build/locale/$$lang/LC_MESSAGES; \
		msgfmt --check -o build/locale/$$lang/LC_MESSAGES/aurora.mo $$po || exit 1; \
	done
	mkdir -p build/locale
	$(PYTHON) po/gtklock-catalogs.py po/gtklock.json build/locale

# Three series of four pictures (dawn, day, dusk, night) in
# branding/wallpapers/SERIES/, installed as aurora-SERIES-PHASE.png.
wallpapers: build/wallpapers/.stamp

build/wallpapers/.stamp: $(wildcard $(BRANDING)/wallpapers/*/*.png)
	rm -rf build/wallpapers && mkdir -p build/wallpapers
	for dir in $(BRANDING)/wallpapers/*/; do \
		series=$$(basename $$dir); \
		for picture in $$dir*.png; do \
			cp $$picture build/wallpapers/aurora-$$series-$$(basename $$picture); \
		done; \
	done
	touch $@

sounds: build/sounds/.stamp

build/sounds/.stamp: $(BRANDING)/sounds/generate.py
	rm -rf build/sounds
	$(PYTHON) $(BRANDING)/sounds/generate.py build/sounds
	touch $@

# Regenerate the translation template from the sources.
pot:
	xgettext --from-code=UTF-8 --language=Python --keyword=_ --keyword=N_ \
		--keyword=ngettext:1,2 --add-comments=TRANSLATORS --flag=_:1:no-python-format \
		--package-name=aurora -o po/aurora.pot $$(find aurora -name '*.py' | sort)
	# App names and descriptions in Launchpad, the dock and menus (the
	# hidden helpers' entries are never shown).
	xgettext --from-code=UTF-8 --language=Desktop -k -kName -kGenericName -kComment -j \
		-o po/aurora.pot $$(ls data/applications/*.desktop | grep -v -e installer-window -e io.calamares)
	for po in po/*.po; do [ -e "$$po" ] && msgmerge -q -U --backup=none $$po po/aurora.pot; done; true

check:
	$(PYTHON) -m py_compile $$(find aurora -name '*.py') bin/aurora-shell
