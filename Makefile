APP_NAME = deepseek_free_rust_bot
VERSION = $(shell grep '^version =' Cargo.toml | sed -E 's/.*"([^"]+)".*/\1/')

.PHONY: build
build:
	cargo build --release

.PHONY: run
run:
	cargo run --release

.PHONY: check
check:
	cargo check

.PHONY: clean
clean:
	cargo clean

.PHONY: release
release: build
	@echo "=== Creating GitHub release v$(VERSION) ==="
	gh release create v$(VERSION) \
		./target/release/$(APP_NAME) \
		--title "v$(VERSION)" \
		--notes "Release $(VERSION)"
	@echo "=== Done! https://github.com/raebaexxx/deepseek_free_rust_bot_test/releases/tag/v$(VERSION) ==="

.PHONY: bump-version
bump-version:
	@echo "Current version: $(VERSION)"
	@read -p "New version: " newver; \
	sed -i "s/^version = \".*\"/version = \"$$newver\"/" Cargo.toml; \
	sed -i "s/^version = \".*\"/version = \"$$newver\"/" Cargo.lock 2>/dev/null || true; \
	git add Cargo.toml && git commit -m "Bump version to $$newver"
