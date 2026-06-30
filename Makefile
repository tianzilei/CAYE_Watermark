.PHONY: build run clean install dev

# Build the standalone WebUI executable
build:
	pyinstaller caye-watermark-web.spec --clean --noconfirm

# Run the built executable
run: build
	./dist/caye-watermark-web/caye-watermark-web

# Run in development mode (no build)
dev:
	python -m caye_watermark.webui

# Install package in editable mode
install:
	pip install -e .

# Remove build artifacts
clean:
	rm -rf build dist *.spec.bak
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
