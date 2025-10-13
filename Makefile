PYTHON ?= python3
MAIN_MODULE := nebula_installer/__main__.py
BUILD_DIR := build

.PHONY: all build clean

all: build

build:
	$(PYTHON) -m nuitka --standalone --output-dir=$(BUILD_DIR) $(MAIN_MODULE)

clean:
	rm -rf $(BUILD_DIR)
