PYTHON ?= python3
MAIN_MODULE := nebula_installer/__main__.py
BUILD_DIR := build
APP_MODULE := nebula_installer
APP_NAME := nebula-installer
BINARY := $(BUILD_DIR)/$(APP_MODULE).bin
DIST_DIR := $(BUILD_DIR)/$(APP_MODULE).dist
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

clean:
	rm -rf $(BUILD_DIR)
