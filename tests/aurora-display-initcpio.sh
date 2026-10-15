#!/bin/bash
# omarchy-aurora-firmware's aurora-display mkinitcpio hook: appledrm goes into
# every image, autodetect or not, and the MacBook Neo loads it before udev
# coldplug so a USB-C external display shows the passphrase prompt with the lid
# closed. Every other machine is left to udev, and a failed load never fails
# the unit or the early hook.
set -euo pipefail

REPO_ROOT=$(realpath "${BASH_SOURCE[0]%/*}/..")
RECIPE=$REPO_ROOT/pkgbuilds/omarchy-aurora-firmware
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() {
  echo "not ok - $1" >&2
  [[ $# -lt 2 ]] || printf '%s\n' "$2" >&2
  exit 1
}
pass() {
  echo "ok - $1"
}

for file in aurora-display.install aurora-display.hook aurora-display-early.sh; do
  bash -n "$RECIPE/$file" || fail "$file parses"
done
pass 'hook, runscript and early loader parse'

grep -qx 'HOOKS+=(aurora-display)' "$RECIPE/96-aurora-display.conf" ||
  fail 'the drop-in appends the hook'
pass 'the drop-in appends the hook'

unit=$RECIPE/aurora-display-early.service
grep -qx 'DefaultDependencies=no' "$unit" && grep -qx 'Type=oneshot' "$unit" &&
  grep -qx 'ExecStart=/usr/lib/omarchy/initcpio/aurora-display-early.sh' "$unit" ||
  fail 'the unit runs the early loader once, outside the default dependencies'
if grep -qE '^(Before|Requires|RequiredBy|WantedBy)=.*(udev|cryptsetup|initrd-root)' "$unit"; then
  fail 'the unit must not hold up udev, cryptsetup or the root device'
fi
pass 'the unit runs once and holds up nothing'

# build() under stub mkinitcpio helpers.
calls=$TEST_ROOT/calls
(
  add_module() { echo "add_module $*" >>"$calls"; }
  add_binary() { echo "add_binary $*" >>"$calls"; }
  add_file() { echo "add_file $*" >>"$calls"; }
  add_symlink() { echo "add_symlink $*" >>"$calls"; }
  add_runscript() { echo "add_runscript" >>"$calls"; }
  # shellcheck source=/dev/null
  . "$RECIPE/aurora-display.install"
  build
)
for expected in \
  "add_module appledrm?" \
  "add_binary modprobe" \
  "add_binary grep" \
  "add_file /usr/lib/omarchy/initcpio/aurora-display-early.sh" \
  "add_file /usr/lib/omarchy/initcpio/aurora-display-early.service /usr/lib/systemd/system/aurora-display-early.service 644" \
  "add_symlink /usr/lib/systemd/system/sysinit.target.wants/aurora-display-early.service ../aurora-display-early.service" \
  "add_runscript"; do
  grep -qxF -- "$expected" "$calls" || fail "build() runs: $expected" "$(cat "$calls")"
done
pass 'build() adds appledrm (optional), the loader, the unit and the runscript'

# The early loader on fixture machines.
cat >"$TEST_ROOT/modprobe" <<'EOF'
#!/bin/sh
echo "$*" >>"$MODPROBE_LOG"
exit "${MODPROBE_STATUS:-0}"
EOF
chmod +x "$TEST_ROOT/modprobe"
early() {
  : >"$TEST_ROOT/log"
  AURORA_DT_COMPATIBLE=$TEST_ROOT/compatible AURORA_MODPROBE=$TEST_ROOT/modprobe \
    MODPROBE_LOG=$TEST_ROOT/log MODPROBE_STATUS=${1:-0} \
    "$RECIPE/aurora-display-early.sh" 2>"$TEST_ROOT/err"
}
printf 'apple,j700\0apple,t8140\0apple,arm-platform\0' >"$TEST_ROOT/compatible"
early || fail 'the Neo loader succeeds'
[[ $(<"$TEST_ROOT/log") == '-q appledrm' ]] || fail 'the Neo loads appledrm' "$(<"$TEST_ROOT/log")"
pass 'the Neo loads appledrm early'
early 1 || fail 'a failed load does not fail the unit'
grep -q 'udev will load it' "$TEST_ROOT/err" || fail 'a failed load is reported'
pass 'a failed load is reported and leaves the rest to udev'
printf 'apple,j413\0apple,t8112\0apple,arm-platform\0' >"$TEST_ROOT/compatible"
early && [[ ! -s $TEST_ROOT/log ]] || fail 'another Mac is left to udev'
rm -f "$TEST_ROOT/compatible"
early && [[ ! -s $TEST_ROOT/log ]] || fail 'a machine without a device tree is left alone'
pass 'other machines are left to udev'

# The runscript only calls the loader.
(
  # shellcheck source=/dev/null
  . "$RECIPE/aurora-display.hook"
  [[ $(type -t run_earlyhook) == function ]]
) || fail 'the runscript defines run_earlyhook'
pass 'the busybox runscript defines run_earlyhook'
