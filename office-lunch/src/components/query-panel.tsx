"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { onQueries, type QueryEntry } from "@/lib/api";
import { Button } from "./ui";

const engineStyle = {
  teradata: { label: "Teradata", className: "bg-accent-soft text-accent" },
  qdrant: { label: "Qdrant", className: "bg-vec-soft text-vec" },
} as const;

// Khung "Xem truy vấn": liệt kê các truy vấn Teradata/Qdrant mà trang hiện tại vừa gọi.
export function QueryPanel() {
  const path = usePathname();
  const [entries, setEntries] = useState<QueryEntry[]>([]);
  const [open, setOpen] = useState(false);

  // Mỗi endpoint chỉ giữ lần gọi mới nhất để khung không bị lặp
  useEffect(
    () => onQueries((e) => setEntries((prev) => [...e, ...prev.filter((p) => p.endpoint !== e[0]?.endpoint)].slice(0, 40))),
    [],
  );
  useEffect(() => setEntries([]), [path]);

  const counts = {
    teradata: entries.filter((e) => e.engine === "teradata").length,
    qdrant: entries.filter((e) => e.engine === "qdrant").length,
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-[calc(1rem+env(safe-area-inset-bottom,0px))] right-[calc(1rem+env(safe-area-inset-right,0px))] z-30 flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-sm font-medium text-bg shadow-lg"
      >
        Xem truy vấn
        <span className="rounded-full bg-bg/20 px-1.5 text-xs tabular-nums">{entries.length}</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={() => setOpen(false)}>
          <aside
            role="dialog"
            aria-label="Truy vấn cơ sở dữ liệu"
            onClick={(e) => e.stopPropagation()}
            className="flex h-full w-full max-w-xl flex-col bg-bg pb-[env(safe-area-inset-bottom,0px)] pt-[env(safe-area-inset-top,0px)] shadow-2xl"
          >
            <header className="flex items-start justify-between gap-4 border-b border-line p-5">
              <div>
                <h2 className="font-semibold">Truy vấn của trang này</h2>
                <p className="mt-1 text-xs text-muted">
                  {counts.teradata} Teradata · {counts.qdrant} Qdrant. Truy vấn đã thực thi; tham số nhạy cảm được ẩn. Header giới hạn 6 KB.
                </p>
              </div>
              <Button variant="quiet" onClick={() => setOpen(false)}>Đóng</Button>
            </header>
            <ol className="flex-1 overflow-y-auto p-5">
              {entries.length === 0 && <li className="text-sm text-muted">Chưa có truy vấn nào. Thao tác trên trang để xem.</li>}
              {entries.map((q) => (
                <li key={q.id} className="mb-5 flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className={`rounded px-1.5 py-0.5 font-medium ${engineStyle[q.engine].className}`}>{engineStyle[q.engine].label}</span>
                    <span className="font-medium">{q.title}</span>
                    {q.durationMs !== undefined && <span>{q.durationMs.toFixed(2)} ms</span>}
                    {q.rows !== undefined && <span className="text-muted">· {q.rows} dòng</span>}
                  </div>
                  <pre className="overflow-x-auto rounded-xl bg-surface-2 p-3 font-mono text-xs leading-relaxed">{q.text}</pre>
                  <span className="font-mono text-[11px] text-muted">{q.endpoint}</span>
                </li>
              ))}
            </ol>
          </aside>
        </div>
      )}
    </>
  );
}
