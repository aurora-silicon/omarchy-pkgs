# m1n1-aurora

m1n1 from aurora-silicon/m1n1 `aurora-wip` (f3ac615eb1376d3bbba24cd84c414b9e41892adb), with no source patches, plus the Omarchy boot logos. This is the Stage 2 m1n1 of the MacBook Neo (J700) beta. The README in omarchy-mac `feat/neo` names f3ac615 as the m1n1 of the first qualified Neo display defaults.

The earlier 1.6.1.aurora1 build patched alias fallbacks for the USB4 tunables into 06a4601. f3ac615 already falls back to `usb4-N-acio` and `usb4-N-nhi`. It does **not** fall back to `usb4-N-pcie-adapter`, so on M1 and M2 the PCIe adapter tunables are not applied until aurora-wip adds that fallback. Qualify USB4 PCIe tunnelling on the M1 Pro and M2 Max before this build reaches them.

It is built with a pinned rustup toolchain (1.89.0, with the prebuilt `aarch64-unknown-none-softfloat` target). Building core from rust-src with a newer Rust (`BUILDSTD=1`, Rust 1.99) leaves an undefined reference to `wcslen`.

## Pairing with linux-aurora

- It provides `m1n1=1.6.1.aurora20261015`, which satisfies linux-aurora's `m1n1>=1.6.1`, and conflicts with asahi-alarm's `m1n1`. pacman prefers a package literally named `m1n1` over a provider, so an Aurora transaction names `m1n1-aurora` explicitly and accepts its conflict with `m1n1` (`--ask 4` under `--noconfirm`).
- It owns `/usr/lib/asahi-boot/m1n1.bin`. asahi-scripts' `95-m1n1-install.hook` runs `update-m1n1` whenever that file, `/usr/lib/modules/*/dtbs/*` or U-Boot changes. `update-m1n1` writes m1n1, the device trees and gzipped U-Boot into `m1n1/boot.bin` on the system ESP. By default asahi-alarm takes the device trees from the newest `/lib/modules/*-ARCH/dtbs`. That is why linux-aurora's release ends in `-ARCH`. `/etc/default/update-m1n1` overrides are left alone.
- Raising linux-aurora's `_m1n1_version` above 1.6.1 needs an m1n1-aurora whose provided version satisfies it, and that m1n1-aurora must be released first.

## Qualification

Each bump is cold-boot qualified on the M1 Pro and the M2 Max, and from this one on also on the MacBook Neo. Check package installation, the hook rebuilding `boot.bin`, the logo, physical boot and two external displays. A successful build is not hardware acceptance.
