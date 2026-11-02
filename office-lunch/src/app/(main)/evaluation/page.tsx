"use client";
import { PageHead, Section, card } from "@/components/ui";
import { useFetch } from "@/lib/hooks";
type Result = {
  seed: number;
  method: string;
  accuracy: number;
  f1: number;
  trainSeconds: number;
  confusion: { tp: number; tn: number; fp: number; fn: number };
};
type Evaluation = {
  dataset?: {
    transactions: number;
    yes: number;
    no: number;
    uniqueItems: number;
  };
  status: string;
  runId?: string;
  datasetHash?: string;
  adaptation?: string;
  results: Result[];
  dimension?: number;
  epochs?: number;
  minsup?: number;
  seeds?: number[];
};
type Summary = {
  engine: string;
  concurrency: number;
  repeat: number;
  p50Ms: number | null;
  p95Ms: number | null;
  p99Ms: number | null;
  throughput: number;
  errorRate: number;
  recall: number | null;
  quality: { accuracy: number; f1: number } | null;
};
type Benchmark = {
  annotations?: { trainingWarning?: string };
  runId: string;
  trainingRunId: string;
  seed: number;
  k: number;
  train: number;
  test: number;
  datasetHash: string;
  topology: { note: string };
  summaries: Summary[];
};
const pct = (x: number) => `${(x * 100).toFixed(2)}%`;
const mean = (a: number[]) => a.reduce((s, x) => s + x, 0) / a.length;
export default function EvaluationPage() {
  const evaluation = useFetch<Evaluation>("/api/evaluation");
  const benchmarks = useFetch<Benchmark[]>("/api/benchmarks");
  const e = evaluation.data;
  const methods = [...new Set(e?.results.map((r) => r.method) ?? [])];
  return (
    <div className="flex flex-col gap-8">
      <PageHead
        title="Đánh giá mô hình và database"
        sub="Kết quả thực nghiệm thật; food gốc tách khỏi dữ liệu demo bổ sung."
      />
      {(evaluation.error || benchmarks.error) && (
        <p role="alert">{evaluation.error || benchmarks.error}</p>
      )}
      <Section title="Chất lượng biểu diễn + LinearSVC">
        {!e || e.status !== "complete" ? (
          <p>
            Chưa có kết quả huấn luyện hoàn tất. Chạy CLI train và activate trên
            sandbox.
          </p>
        ) : (
          <>
            <p className="text-sm text-muted">
              Run {e.runId} · {e.dimension} chiều · {e.epochs} epoch · minsup{" "}
              {e.minsup} · {e.seeds?.length} seed
            </p>
            <p className="my-3 text-sm text-muted">{e.adaptation}</p>
            {e.dataset && (
              <p className="mb-3 text-sm">
                Food: {e.dataset.transactions} giao dịch · {e.dataset.yes} yes /{" "}
                {e.dataset.no} no · {e.dataset.uniqueItems} item. Thời gian
                pipeline gồm học biểu diễn, suy luận test, lưu model và phân
                loại.
              </p>
            )}
            <div className={`${card} overflow-x-auto`}>
              <table className="w-full text-left text-sm">
                <thead>
                  <tr>
                    {[
                      "Phương pháp",
                      "Accuracy TB",
                      "Macro-F1 TB",
                      "Pipeline giây TB",
                    ].map((x) => (
                      <th key={x} className="p-3">
                        {x}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {methods.map((m) => {
                    const rows = e.results.filter((r) => r.method === m);
                    return (
                      <tr key={m}>
                        <td className="p-3">{m}</td>
                        <td>{pct(mean(rows.map((r) => r.accuracy)))}</td>
                        <td>{mean(rows.map((r) => r.f1)).toFixed(4)}</td>
                        <td>
                          {mean(rows.map((r) => r.trainSeconds)).toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <details className="mt-4">
              <summary>Từng seed và confusion matrix</summary>
              <pre className="max-h-96 overflow-auto text-xs">
                {JSON.stringify(e.results, null, 2)}
              </pre>
            </details>
            <p className="mt-3 break-all text-xs">SHA-256: {e.datasetHash}</p>
          </>
        )}
      </Section>
      <Section title="Benchmark Teradata exact / Qdrant exact / Qdrant ANN">
        {!benchmarks.data?.length && (
          <p>Chưa có benchmark hoàn tất. Không thay bằng số liệu giả.</p>
        )}
        {benchmarks.data?.map((b) => (
          <article key={b.runId} className={`${card} my-4 p-4`}>
            <h3 className="font-semibold">{b.runId}</h3>
            {b.annotations?.trainingWarning && (
              <p className="my-3 rounded-lg bg-accent-soft p-3 text-sm">
                {b.annotations.trainingWarning}
              </p>
            )}
            <p className="my-2 text-sm">
              Model {b.trainingRunId}, seed {b.seed} · train {b.train} / test{" "}
              {b.test} · k={b.k}
            </p>
            <p className="text-sm text-muted">{b.topology.note}</p>
            <p className="my-2 text-xs">
              Mỗi dòng là một lượt đo. Dataset nhỏ, cấu hình tài nguyên khác
              nhau. Recall tính so với brute-force float64.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[60rem] text-left text-xs">
                <thead>
                  <tr>
                    {[
                      "Engine",
                      "CC",
                      "Lượt",
                      "p50 ms",
                      "p95 ms",
                      "p99 ms",
                      "QPS",
                      "Lỗi",
                      "Recall@k",
                      "Accuracy",
                      "Macro-F1",
                    ].map((x) => (
                      <th key={x} className="p-2">
                        {x}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {b.summaries.map((s, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="p-2">{s.engine}</td>
                      <td>{s.concurrency}</td>
                      <td>{s.repeat + 1}</td>
                      <td>{s.p50Ms?.toFixed(2) ?? "—"}</td>
                      <td>{s.p95Ms?.toFixed(2) ?? "—"}</td>
                      <td>{s.p99Ms?.toFixed(2) ?? "—"}</td>
                      <td>{s.throughput.toFixed(2)}</td>
                      <td>{pct(s.errorRate)}</td>
                      <td>{s.recall === null ? "—" : pct(s.recall)}</td>
                      <td>{s.quality ? pct(s.quality.accuracy) : "—"}</td>
                      <td>{s.quality?.f1.toFixed(4) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 break-all text-xs">
              Dataset SHA-256: {b.datasetHash}
            </p>
          </article>
        ))}
      </Section>
    </div>
  );
}
