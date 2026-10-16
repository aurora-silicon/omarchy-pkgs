#!/usr/bin/env python3
"""Execute package review regressions without building or booting a kernel."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def shell(script, *args, **kwargs):
    return subprocess.run(['bash', '-c', script, 'fixture', *map(str, args)],
                          text=True, capture_output=True, **kwargs)


class KernelRecipeTests(unittest.TestCase):
    def test_command_line_bindgen_wins_over_kbuild_assignment_in_every_phase(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Makefile').write_text('BINDGEN = ignored-system-bindgen\nprobe:\n\t@echo $(BINDGEN)\n\t@echo $$AURORA_BINDGEN_REAL\n\t@echo $$RUSTUP_TOOLCHAIN\n')
            recipe = ROOT / 'pkgbuilds/linux-aurora/PKGBUILD'
            result = shell('source "$1"; srcdir="$2"; _make -s -f "$2/Makefile" probe', recipe, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [
                str(root / 'bindgen-kernel.py'),
                str(root / 'private-bindgen/rust-bindgen-0.73.2/target/release/bindgen'), '1.85.0'])

    def test_shared_config_keeps_existing_machine_behaviour(self):
        package = ROOT / 'pkgbuilds/linux-aurora'
        recipe = (package / 'PKGBUILD').read_text()
        self.assertIn('cp ../config build/base/.config', recipe)
        self.assertIn("grep -qx 'CONFIG_RUST=y'", recipe)
        self.assertNotIn('j700.config', recipe)
        self.assertNotIn('j700-device-parity.config', recipe)
        original = (package / 'config').read_text()
        fragment = (package / 'neo.config').read_text()
        for setting in ['CONFIG_USB4=m', 'CONFIG_DEBUG_INFO_BTF=y', 'CONFIG_KEXEC_FILE=y',
                        'CONFIG_RELR=y', 'CONFIG_RUST=y']:
            self.assertIn(setting, original)
        for line in fragment.splitlines():
            if line.startswith('CONFIG_'):
                name = line.split('=', 1)[0]
                self.assertNotIn('\n' + name + '=', original, 'Neo fragment overrides shared setting')
        self.assertIn('CONFIG_MT7932_FULLMAC=m', fragment)

    def test_headers_require_resolver_only_when_btf_enabled(self):
        recipe = ROOT / 'pkgbuilds/linux-aurora/PKGBUILD'
        for enabled, resolver, expected in [(False, False, 0), (True, False, 1), (True, True, 0)]:
            with self.subTest(btf=enabled, resolver=resolver), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                output = root / 'linux/build/base'
                output.mkdir(parents=True)
                (output / 'version').write_text('fixture\n')
                (output / '.config').write_text('CONFIG_DEBUG_INFO_BTF=y\n' if enabled else '# CONFIG_DEBUG_INFO_BTF is not set\n')
                if resolver:
                    binary = output / 'tools/bpf/resolve_btfids/resolve_btfids'
                    binary.parent.mkdir(parents=True)
                    binary.write_text('#!/bin/sh\n')
                    binary.chmod(0o755)
                result = shell('''source "$1"
cd "$2"
pkgdir="$2/pkg"; _srcname=linux
install() { :; }; cp() { :; }; rm() { :; }; find() { :; }; _make() { :; }
_package-headers
''', recipe, root)
                self.assertEqual(result.returncode, expected, result.stderr)


class QualificationTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'pkgbuilds/aura/validate-qualification.py'
        spec = importlib.util.spec_from_file_location('qualification', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.record = json.loads(path.with_name('build-qualification.json').read_text())

    def test_current_unqualified_pin_cannot_publish(self):
        with self.assertRaisesRegex(ValueError, 'not hardware-qualified'):
            self.module.validate(self.record, self.record['source_commit'])

    def test_exact_pin_and_all_evidence_are_required(self):
        record = dict(self.record, hardware_tested=True)
        with self.assertRaises(ValueError):
            self.module.validate(record, record['source_commit'])
        record['evidence'] = {gate: {'passed': True, 'report': 'synthetic fixture only'}
                              for gate in ['native_build', 'matched_stage1_stage2_boot', 'repair', 'upgrade']}
        self.module.validate(record, record['source_commit'])
        with self.assertRaises(ValueError):
            self.module.validate(record, '0' * 40)


class FirmwareTests(unittest.TestCase):
    def test_systemd_initrd_is_required_before_installing_any_hook_files(self):
        hook = ROOT / 'pkgbuilds/omarchy-aurora-firmware/aurora-vendor-order.install'
        functions = 'add_binary() { :; }; add_module() { :; }; add_file() { :; }; add_symlink() { :; }; '
        for hooks, expected in [('base udev', 1), ('base systemd', 0)]:
            result = shell(functions + 'source "$1"; read -ra HOOKS <<<"$2"; build', hook, hooks)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_external_hints_are_rate_limited_and_world_does_not_loop(self):
        path = ROOT / 'pkgbuilds/omarchy-aurora-firmware/aurora-regdom-fallback'
        # Source only the function/state; no live iw process or regulatory change.
        setup = path.read_text().split('\n# An initramfs')[0]
        code = setup + '''
calls=0; current=PL
sleep() { SECONDS=$((SECONDS+$1)); }
iw() { if [[ $1 == reg && $2 == get ]]; then echo "country $current:"; else calls=$((calls+1)); current=00; fi; }
fall_back
[[ $calls == 1 ]] || exit 10
current=JP; fall_back
[[ $calls == 2 && $SECONDS -ge 60 ]] || exit 11
# A supported hint arriving during the delay must not be overwritten.
touch "$policy/US.bin"
sleep() { SECONDS=$((SECONDS+$1)); current=US; }
current=PL; fall_back
[[ $calls == 2 && $current == US ]] || exit 12
current=00; fall_back
[[ $calls == 2 ]] || exit 13
'''
        with tempfile.TemporaryDirectory() as temporary:
            result = shell(code, env=dict(os.environ, AURORA_REGDOM_POLICY_DIR=temporary))
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
