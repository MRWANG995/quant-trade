import { InstrumentsClient } from "./InstrumentsClient";
import { fetchApiServer } from "@/lib/api-server";
import type { Instrument } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function InstrumentsPage() {
  try {
    const instruments = await fetchApiServer<Instrument[]>("/api/instruments");
    return <InstrumentsClient instruments={instruments} />;
  } catch {
    return (
      <div className="card">
        <h1 className="text-xl font-bold">行情</h1>
        <p className="mt-2 text-sm text-zinc-500">请先启动后端 API</p>
      </div>
    );
  }
}
