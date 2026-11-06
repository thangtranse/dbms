# Teradata Vantage Express runtime

The VM source images, writable overlays, logs, and installers are intentionally
excluded from Git. The launcher expects the extracted Vantage Express 20.00.28.81
VMDKs under `teradata/runtime/vantage-express`.

The source VMDKs remain read-only in practice: QEMU writes to QCOW2 overlays in
`teradata/runtime/vantage-express/overlays`.

Disk cache uses `writethrough`: QEMU flushes each write before acknowledging it
to the guest. This prioritizes durability and can reduce write throughput; it
does not repair an already damaged WAL or establish the cause of an earlier
failure. See [QEMU disk cache documentation](https://www.qemu.org/docs/master/system/qemu-manpage.html).
Always shut down the guest cleanly before host maintenance; do not kill QEMU
or copy live writable overlays as if they were consistent backups.

```bash
./teradata/bin/start-vantage.sh
./teradata/bin/status-vantage.sh
./teradata/bin/stop-vantage.sh
```

Network forwards:

- Teradata SQL: host `0.0.0.0:1025` to guest `1025`
- Guest SSH: host `127.0.0.1:22022` to guest `22`

