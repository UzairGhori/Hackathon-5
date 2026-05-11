"use client";

import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  AlertTriangle,
  ChevronLeft,
  Clock,
  User,
  Tag,
  Ticket as TicketIcon,
  Search,
  ArrowRight,
} from "lucide-react";
import { getTickets, getTicket, getTicketEvents } from "@/lib/api";
import type { Ticket, TicketEvent } from "@/lib/types";

const TABS: { label: string; value: string; count?: boolean }[] = [
  { label: "All Tickets", value: "all" },
  { label: "Open", value: "open" },
  { label: "In Progress", value: "in_progress" },
  { label: "Escalated", value: "escalated" },
  { label: "Resolved", value: "resolved" },
  { label: "Closed", value: "closed" },
];

const STATUS_STYLES: Record<string, string> = {
  open: "bg-sky-50 text-sky-700 ring-1 ring-sky-200",
  in_progress: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  escalated: "bg-red-50 text-red-700 ring-1 ring-red-200",
  resolved: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  closed: "bg-gray-100 text-gray-600 ring-1 ring-gray-200",
  waiting_on_customer: "bg-violet-50 text-violet-700 ring-1 ring-violet-200",
};

const PRIORITY_STYLES: Record<string, string> = {
  low: "bg-gray-100 text-gray-600",
  medium: "bg-sky-50 text-sky-700",
  high: "bg-amber-50 text-amber-700",
  critical: "bg-red-50 text-red-700",
};

const PRIORITY_DOT: Record<string, string> = {
  low: "bg-gray-400",
  medium: "bg-sky-500",
  high: "bg-amber-500",
  critical: "bg-red-500",
};

const EVENT_COLORS: Record<string, string> = {
  created: "bg-sky-500",
  status_changed: "bg-amber-500",
  priority_changed: "bg-violet-500",
  assigned: "bg-cyan-500",
  escalated: "bg-red-500",
  note_added: "bg-gray-400",
  resolved: "bg-emerald-500",
  closed: "bg-gray-500",
};

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [activeTab, setActiveTab] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [events, setEvents] = useState<TicketEvent[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTickets(activeTab === "all" ? undefined : activeTab);
      setTickets(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    const init = async () => {
      await loadTickets();
    };
    init();
  }, [loadTickets]);

  const openDetail = async (ticket: Ticket) => {
    setDetailLoading(true);
    try {
      const [t, ev] = await Promise.all([
        getTicket(ticket.id),
        getTicketEvents(ticket.id).catch(() => []),
      ]);
      setSelectedTicket(t);
      setEvents(ev);
    } catch {
      setSelectedTicket(ticket);
      setEvents([]);
    } finally {
      setDetailLoading(false);
    }
  };

  // Detail view
  if (selectedTicket) {
    return (
      <div className="max-w-4xl space-y-6 animate-fade-in-up">
        <button
          onClick={() => setSelectedTicket(null)}
          className="group flex items-center gap-2 text-muted-foreground hover:text-accent transition-colors text-sm font-medium"
        >
          <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Tickets
        </button>

        {detailLoading ? (
          <div className="flex justify-center py-20">
            <RefreshCw className="w-6 h-6 text-accent animate-spin" />
          </div>
        ) : (
          <>
            {/* Ticket Header Card */}
            <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm">
              <div className="bg-gradient-to-r from-[#0c4a6e] to-[#1e3a5f] px-6 py-5">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sky-300/70 text-xs font-medium uppercase tracking-wider mb-1">
                      Ticket Details
                    </p>
                    <h1 className="text-xl font-bold text-white">
                      {selectedTicket.subject}
                    </h1>
                  </div>
                  <div className="flex gap-2">
                    <span
                      className={`px-3 py-1.5 text-xs rounded-lg font-semibold ${
                        STATUS_STYLES[selectedTicket.status] ?? STATUS_STYLES.open
                      }`}
                    >
                      {selectedTicket.status.replace(/_/g, " ")}
                    </span>
                    <span
                      className={`px-3 py-1.5 text-xs rounded-lg font-semibold flex items-center gap-1.5 ${
                        PRIORITY_STYLES[selectedTicket.priority] ??
                        PRIORITY_STYLES.medium
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          PRIORITY_DOT[selectedTicket.priority] ?? "bg-sky-500"
                        }`}
                      />
                      {selectedTicket.priority}
                    </span>
                  </div>
                </div>
              </div>
              <div className="p-6">
                {selectedTicket.description && (
                  <p className="text-muted-foreground text-sm mb-5 leading-relaxed">
                    {selectedTicket.description}
                  </p>
                )}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    {
                      icon: Tag,
                      label: "Channel",
                      value: selectedTicket.channel,
                      capitalize: true,
                    },
                    {
                      icon: User,
                      label: "Assigned To",
                      value: selectedTicket.assigned_to ?? "Unassigned",
                    },
                    {
                      icon: Clock,
                      label: "Created",
                      value: new Date(
                        selectedTicket.created_at
                      ).toLocaleDateString(),
                    },
                    {
                      icon: Clock,
                      label: "Last Updated",
                      value: new Date(
                        selectedTicket.updated_at
                      ).toLocaleDateString(),
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="bg-muted/40 rounded-xl p-3.5"
                    >
                      <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
                        <item.icon className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-medium uppercase tracking-wider">
                          {item.label}
                        </span>
                      </div>
                      <p
                        className={`text-sm font-semibold text-foreground ${
                          item.capitalize ? "capitalize" : ""
                        }`}
                      >
                        {item.value}
                      </p>
                    </div>
                  ))}
                </div>
                {selectedTicket.tags.length > 0 && (
                  <div className="flex gap-2 mt-4 flex-wrap">
                    {selectedTicket.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2.5 py-1 text-xs bg-accent/5 text-accent rounded-lg font-medium ring-1 ring-accent/10"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Audit Trail */}
            <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
              <h2 className="text-base font-semibold mb-6 flex items-center gap-2">
                <Clock className="w-4 h-4 text-muted-foreground" />
                Audit Trail
              </h2>
              {events.length > 0 ? (
                <div className="relative ml-3">
                  <div className="absolute left-[7px] top-3 bottom-3 w-0.5 bg-border" />
                  <div className="space-y-5">
                    {events.map((event) => (
                      <div key={event.id} className="flex gap-4 relative">
                        <div
                          className={`w-4 h-4 rounded-full flex-shrink-0 mt-0.5 ring-4 ring-card ${
                            EVENT_COLORS[event.event_type] ?? "bg-gray-400"
                          }`}
                        />
                        <div className="flex-1 min-w-0 bg-muted/30 rounded-xl px-4 py-3">
                          <div className="flex items-center gap-2 text-sm">
                            <span className="font-semibold text-foreground capitalize">
                              {event.event_type.replace(/_/g, " ")}
                            </span>
                            <span className="text-muted-foreground">by</span>
                            <span className="font-medium text-accent">
                              {event.actor}
                            </span>
                          </div>
                          {event.note && (
                            <p className="text-sm text-muted-foreground mt-1">
                              {event.note}
                            </p>
                          )}
                          {event.old_value && event.new_value && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1.5 font-mono">
                              <span className="bg-red-50 text-red-600 px-1.5 py-0.5 rounded">
                                {JSON.stringify(event.old_value)}
                              </span>
                              <ArrowRight className="w-3 h-3" />
                              <span className="bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded">
                                {JSON.stringify(event.new_value)}
                              </span>
                            </div>
                          )}
                          <p className="text-[11px] text-muted-foreground/70 mt-1.5">
                            {new Date(event.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-muted-foreground text-sm text-center py-8">
                  No audit events recorded yet.
                </p>
              )}
            </div>
          </>
        )}
      </div>
    );
  }

  // List view
  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Support Tickets</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Manage and track all customer support requests
          </p>
        </div>
        <button
          onClick={loadTickets}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent text-white rounded-xl font-medium hover:bg-accent-light transition-colors shadow-sm text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 bg-muted/50 border border-border rounded-xl p-1.5">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className={`px-4 py-2 text-sm rounded-lg transition-all font-medium ${
              activeTab === tab.value
                ? "bg-white text-foreground shadow-sm ring-1 ring-border"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl">
          <AlertTriangle className="w-5 h-5 text-danger" />
          <p className="text-danger text-sm font-medium">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex justify-center py-20">
          <RefreshCw className="w-6 h-6 text-accent animate-spin" />
        </div>
      ) : tickets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-card border border-border rounded-2xl">
          <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-4">
            <Search className="w-8 h-8 text-muted-foreground" />
          </div>
          <p className="text-foreground font-semibold">No tickets found</p>
          <p className="text-muted-foreground text-sm mt-1">
            Submit a message from Live Support to create tickets
          </p>
        </div>
      ) : (
        /* Tickets Table */
        <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground uppercase tracking-wider bg-muted/30 border-b border-border">
                  <th className="px-6 py-3.5 font-semibold">Subject</th>
                  <th className="px-6 py-3.5 font-semibold">Status</th>
                  <th className="px-6 py-3.5 font-semibold">Priority</th>
                  <th className="px-6 py-3.5 font-semibold">Channel</th>
                  <th className="px-6 py-3.5 font-semibold">Assigned To</th>
                  <th className="px-6 py-3.5 font-semibold">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    onClick={() => openDetail(ticket)}
                    className="hover:bg-muted/20 cursor-pointer transition-colors group"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-accent/5 flex items-center justify-center flex-shrink-0">
                          <TicketIcon className="w-4 h-4 text-accent" />
                        </div>
                        <span className="font-medium text-foreground group-hover:text-accent transition-colors max-w-xs truncate">
                          {ticket.subject}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex px-2.5 py-1 text-xs rounded-lg font-semibold ${
                          STATUS_STYLES[ticket.status] ?? STATUS_STYLES.open
                        }`}
                      >
                        {ticket.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg font-medium ${
                          PRIORITY_STYLES[ticket.priority] ??
                          PRIORITY_STYLES.medium
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            PRIORITY_DOT[ticket.priority] ?? "bg-sky-500"
                          }`}
                        />
                        {ticket.priority}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex px-2.5 py-1 text-xs font-medium rounded-lg bg-muted text-muted-foreground capitalize">
                        {ticket.channel}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-muted-foreground font-medium">
                      {ticket.assigned_to ?? (
                        <span className="italic text-muted-foreground/50">
                          Unassigned
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground whitespace-nowrap text-xs">
                      {new Date(ticket.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-3 border-t border-border bg-muted/20">
            <p className="text-xs text-muted-foreground">
              Showing {tickets.length} ticket{tickets.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
