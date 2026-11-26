PYTHON ?= python3
MAIN_MODULE := nebula_installer/__main__.py
ENTRY_NAME := $(basename $(notdir $(MAIN_MODULE)))
BUILD_DIR := build
APP_MODULE := nebula_installer
APP_NAME := nebula-installer
BINARY = $(DIST_DIR)/$(APP_MODULE)
DIST_DIR := $(BUILD_DIR)/$(ENTRY_NAME).dist
PREFIX ?= /usr/local

.PHONY: all build clean install

all: build

build:
	$(PYTHON) -m nuitka --standalone \
		--include-package=$(APP_MODULE) \
		--output-dir=$(BUILD_DIR) \
		--output-filename=$(APP_MODULE) \
		$(MAIN_MODULE)

install: build
	install -d $(DESTDIR)$(PREFIX)/lib/$(APP_NAME)
	cp -a $(DIST_DIR)/. $(DESTDIR)$(PREFIX)/lib/$(APP_NAME)/
	install -d $(DESTDIR)$(PREFIX)/bin
	install -m755 $(BINARY) $(DESTDIR)$(PREFIX)/bin/$(APP_NAME)
	install -d $(DESTDIR)$(PREFIX)/share/applications
	install -m644 assets/org.lpm.NebulaInstaller.desktop $(DESTDIR)$(PREFIX)/share/applications/

clean:
	rm -rf $(BUILD_DIR)
