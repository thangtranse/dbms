// Trace của các truy vấn backend đã thực thi; không chứa bind values hoặc credentials.
export type Engine = "teradata" | "qdrant";
export interface QueryLog {
  engine: Engine;
  title: string;
  text: string;
  rows?: number;
  durationMs?: number;
}
export const QUERY_HEADER = "x-ol-queries";
