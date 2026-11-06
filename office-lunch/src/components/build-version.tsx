import { buildInfo } from "@/lib/build-info";

export function BuildVersion() {
  return (
    <div aria-label="Thông tin bản build" className="flex flex-wrap justify-end gap-x-3 gap-y-1 border-b border-line px-4 py-1 text-[11px] text-muted">
      <a href="/build-info" title={`Commit: ${buildInfo.commit}`} className="hover:text-ink">
        Phiên bản <code>{buildInfo.version}</code>
      </a>
      {buildInfo.builtAt && (
        <time dateTime={buildInfo.builtAt}>
          Build {buildInfo.builtAt.replace("T", " ").replace(/\.\d+Z$/, " UTC")}
        </time>
      )}
    </div>
  );
}
