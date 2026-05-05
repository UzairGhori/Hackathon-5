import type {
  DBStats,
  DashboardMetrics,
  DemoProcessRequest,
  DemoProcessResponse,
  SeedResponse,
  Ticket,
  TicketEvent,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    // Parse FastAPI validation errors into readable messages
    try {
      const json = JSON.parse(text);
      if (json.detail && Array.isArray(json.detail)) {
        const msgs = json.detail.map(
          (d: { loc?: string[]; msg?: string }) =>
            `${d.loc?.slice(1).join(".") ?? "field"}: ${d.msg}`
        );
        throw new Error(msgs.join("\n"));
      }
      if (json.detail && typeof json.detail === "string") {
        throw new Error(json.detail);
      }
    } catch (e) {
      if (e instanceof Error && !e.message.startsWith("API")) throw e;
    }
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// Demo endpoints
export function getDemoStats(): Promise<DBStats> {
  return fetchJSON("/api/v1/demo/stats");
}

export function seedDemoData(): Promise<SeedResponse> {
  return fetchJSON("/api/v1/demo/seed", { method: "POST" });
}

export function processMessage(data: DemoProcessRequest): Promise<DemoProcessResponse> {
  return fetchJSON("/api/v1/demo/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// Tickets
export function getTickets(status?: string, limit = 50): Promise<Ticket[]> {
  const params = new URLSearchParams();
  if (status && status !== "all") params.set("status", status);
  params.set("limit", String(limit));
  return fetchJSON(`/api/v1/tickets?${params}`);
}

export function getTicket(id: string): Promise<Ticket> {
  return fetchJSON(`/api/v1/tickets/${id}`);
}

export function getTicketEvents(id: string): Promise<TicketEvent[]> {
  return fetchJSON(`/api/v1/tickets/${id}/events`);
}

// Metrics
export function getDashboardMetrics(hours?: number): Promise<DashboardMetrics> {
  const params = hours ? `?hours=${hours}` : "";
  return fetchJSON(`/api/v1/metrics/dashboard${params}`);
}
