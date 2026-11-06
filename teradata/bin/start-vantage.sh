#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_dir="${VANTAGE_RUNTIME_DIR:-$project_dir/teradata/runtime/vantage-express}"
state_dir="$runtime_dir/state"
overlay_dir="$runtime_dir/overlays"
qemu_bin="${QEMU_SYSTEM_BIN:-/opt/local/bin/qemu-system-x86_64}"
qemu_img="${QEMU_IMG_BIN:-/opt/local/bin/qemu-img}"
prefix="VantageExpress_20.00.28.81_SLES15_20251203053450"
pid_file="$state_dir/vantage.pid"
monitor_socket="$state_dir/vantage-monitor.sock"
serial_log="$state_dir/vantage-serial.log"

mkdir -p "$state_dir" "$overlay_dir"

if [[ -s "$pid_file" ]] && kill -0 "$(<"$pid_file")" 2>/dev/null; then
  echo "Vantage is already running (PID $(<"$pid_file"))"
  exit 0
fi

for tool in "$qemu_bin" "$qemu_img"; do
  [[ -x "$tool" ]] || { echo "Missing executable: $tool" >&2; exit 1; }
done

for disk in 1 2 3; do
  source_disk="$runtime_dir/$prefix-disk$disk.vmdk"
  overlay_disk="$overlay_dir/disk$disk.qcow2"
  [[ -f "$source_disk" ]] || { echo "Missing source disk: $source_disk" >&2; exit 1; }
  if [[ ! -f "$overlay_disk" ]]; then
    "$qemu_img" create -f qcow2 -F vmdk -b "$source_disk" "$overlay_disk"
  fi
done

rm -f "$monitor_socket" "$pid_file"

"$qemu_bin" \
  -name vantage-express \
  -machine q35,accel=hvf \
  -cpu host \
  -smp 2 \
  -m 8192 \
  -boot order=c \
  -drive "file=$overlay_dir/disk3.qcow2,if=none,id=disk0,format=qcow2,cache=writethrough" \
  -device ide-hd,drive=disk0,bus=ide.0 \
  -drive "file=$overlay_dir/disk1.qcow2,if=none,id=disk1,format=qcow2,cache=writethrough" \
  -device ide-hd,drive=disk1,bus=ide.1 \
  -drive "file=$overlay_dir/disk2.qcow2,if=none,id=disk2,format=qcow2,cache=writethrough" \
  -device ide-hd,drive=disk2,bus=ide.2 \
  -netdev user,id=net0,hostfwd=tcp:0.0.0.0:1025-:1025,hostfwd=tcp:127.0.0.1:22022-:22 \
  -device vmxnet3,netdev=net0,mac=52:54:00:20:00:81 \
  -display none \
  -serial "file:$serial_log" \
  -monitor "unix:$monitor_socket,server=on,wait=off" \
  -pidfile "$pid_file" \
  -daemonize

echo "Vantage started (PID $(<"$pid_file")); serial log: $serial_log"

