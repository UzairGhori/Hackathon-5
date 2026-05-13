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
  Shield,
  CheckCircle,
} from "lucide-react";
import { getTickets, getTicket, getTicketEvents } from "@/lib/api";
import type { Ticket, TicketEvent } from "@/lib/types";

const TABS: { label: string; value: string; count?: boolean }[] = [
  { label: "All Missions", value: "all" },
  { label: "Open", value: "open" },
  { label: "In Progress", value: "in_progress" },
  { label: "Escalated", value: "escalated" },
  { label: "Resolved", value: "resolved" },
  { label: "Closed", value: "closed" },
];

const STATUS_STYLES: Record<string, string> = {
  open: "bg-[#002d5a] text-white",
  in_progress: "bg-amber-500 text-white",
  escalated: "bg-rose-600 text-white shadow-lg shadow-rose-600/20",
  resolved: "bg-shaheen-emerald text-white",
  closed: "bg-slate-500 text-white",
  waiting_on_customer: "bg-violet-600 text-white",
};

const PRIORITY_STYLES: Record<string, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-sky-100 text-[#002d5a]",
  high: "bg-amber-100 text-amber-700",
  critical: "bg-rose-100 text-rose-700 font-black",
};

const PRIORITY_DOT: Record<string, string> = {
  low: "bg-slate-400",
  medium: "bg-[#002d5a]",
  high: "bg-amber-500",
  critical: "bg-rose-600",
};

const EVENT_COLORS: Record<string, string> = {
  created: "bg-sky-500",
  status_changed: "bg-amber-500",
  priority_changed: "bg-violet-500",
  assigned: "bg-cyan-500",
  escalated: "bg-rose-600",
  note_added: "bg-slate-400",
  resolved: "bg-shaheen-emerald",
  closed: "bg-slate-500",
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
      <div className="max-w-5xl space-y-10 animate-fade-in-up pb-20">
        <button
          onClick={() => setSelectedTicket(null)}
          className="group flex items-center gap-3 text-slate-400 hover:text-[#002d5a] transition-all text-xs font-black uppercase tracking-widest"
        >
          <ChevronLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          Return to Command List
        </button>

        {detailLoading ? (
          <div className="flex flex-col items-center justify-center py-32 gap-6">
            <RefreshCw className="w-10 h-10 text-[#002d5a] animate-spin" />
            <p className="text-[10px] font-black text-slate-300 uppercase tracking-[0.3em]">Retrieving Intelligence...</p>
          </div>
        ) : (
          <>
            {/* Ticket Header Card */}
            <div className="bg-white border border-slate-200 rounded-[3rem] overflow-hidden shadow-2xl">
              <div className="bg-[#002d5a] px-10 py-8 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -mr-20 -mt-20 blur-3xl pointer-events-none" />
                <div className="relative z-10 flex flex-col md:flex-row items-start justify-between gap-6">
                  <div>
                    <div className="flex items-center gap-3 mb-3">
                       <Shield className="w-4 h-4 text-shaheen-emerald" />
                       <p className="text-white/40 text-[10px] font-black uppercase tracking-[0.25em]">
                         Mission Intelligence Log
                       </p>
                    </div>
                    <h1 className="text-3xl font-black text-white tracking-tight">
                      {selectedTicket.subject}
                    </h1>
                  </div>
                  <div className="flex gap-3">
                    <span
                      className={`px-5 py-2 text-[10px] rounded-full font-black uppercase tracking-widest shadow-xl ${
                        STATUS_STYLES[selectedTicket.status] ?? STATUS_STYLES.open
                      }`}
                    >
                      {selectedTicket.status.replace(/_/g, " ")}
                    </span>
                    <span
                      className={`px-5 py-2 text-[10px] rounded-full font-black uppercase tracking-widest flex items-center gap-2 shadow-sm ${
                        PRIORITY_STYLES[selectedTicket.priority] ??
                        PRIORITY_STYLES.medium
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          PRIORITY_DOT[selectedTicket.priority] ?? "bg-[#002d5a]"
                        }`}
                      />
                      {selectedTicket.priority}
                    </span>
                  </div>
                </div>
              </div>
              <div className="p-10">
                {selectedTicket.description && (
                  <div className="bg-slate-50 p-8 rounded-[2rem] border border-slate-100 mb-8">
                     <p className="text-[#002d5a] text-base font-medium leading-relaxed italic">
                        &quot;{selectedTicket.description}&quot;
                     </p>
                  </div>
                )}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  {[
                    {
                      icon: Tag,
                      label: "Vector Channel",
                      value: selectedTicket.channel,
                      capitalize: true,
                    },
                    {
                      icon: User,
                      label: "Lead Assignee",
                      value: selectedTicket.assigned_to ?? "Unassigned",
                    },
                    {
                      icon: Clock,
                      label: "Initial Sync",
                      value: new Date(
                        selectedTicket.created_at
                      ).toLocaleDateString(),
                    },
                    {
                      icon: CheckCircle,
                      label: "Last Telemetry",
                      value: new Date(
                        selectedTicket.updated_at
                      ).toLocaleDateString(),
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm"
                    >
                      <div className="flex items-center gap-2 text-slate-400 mb-2">
                        <item.icon className="w-3.5 h-3.5" />
                        <span className="text-[9px] font-black uppercase tracking-widest">
                          {item.label}
                        </span>
                      </div>
                      <p
                        className={`text-sm font-black text-[#002d5a] tracking-tight ${
                          item.capitalize ? "capitalize" : ""
                        }`}
                      >
                        {item.value}
                      </p>
                    </div>
                  ))}
                </div>
                {selectedTicket.tags.length > 0 && (
                  <div className="flex gap-2 mt-8 flex-wrap">
                    {selectedTicket.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-4 py-1.5 text-[9px] bg-[#002d5a]/5 text-[#002d5a] rounded-full font-black uppercase tracking-widest border border-[#002d5a]/10"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Audit Trail */}
            <div className="bg-white border border-slate-200 rounded-[3rem] p-10 shadow-2xl relative overflow-hidden">
               <div className="absolute top-0 right-0 w-64 h-64 bg-[#002d5a]/5 rounded-full -mr-32 -mt-32 blur-3xl pointer-events-none" />
              <h2 className="text-xl font-black text-[#002d5a] mb-10 flex items-center gap-3">
                <Clock className="w-6 h-6 text-[#002d5a]/20" />
                Mission Audit Trail
              </h2>
              {events.length > 0 ? (
                <div className="relative ml-4">
                  <div className="absolute left-[7px] top-4 bottom-4 w-1 bg-slate-100 rounded-full" />
                  <div className="space-y-8">
                    {events.map((event) => (
                      <div key={event.id} className="flex gap-6 relative">
                        <div
                          className={`w-4 h-4 rounded-full flex-shrink-0 mt-1.5 ring-8 ring-white z-10 ${
                            EVENT_COLORS[event.event_type] ?? "bg-slate-400"
                          } shadow-lg`}
                        />
                        <div className="flex-1 min-w-0 bg-slate-50/50 hover:bg-white border border-slate-100 hover:shadow-xl transition-all duration-500 rounded-[2rem] px-8 py-6">
                          <div className="flex items-center justify-between gap-4 mb-2">
                            <div className="flex items-center gap-2 text-sm">
                              <span className="font-black text-[#002d5a] uppercase tracking-tight">
                                {event.event_type.replace(/_/g, " ")}
                              </span>
                              <span className="text-slate-300 font-bold tracking-widest uppercase text-[9px]">Intercepted By</span>
                              <span className="font-black text-shaheen-emerald uppercase tracking-widest text-[10px]">
                                {event.actor}
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-300 font-black uppercase tabular-nums tracking-widest">
                              {new Date(event.created_at).toLocaleString()}
                            </p>
                          </div>
                          {event.note && (
                            <p className="text-sm text-slate-500 font-medium leading-relaxed mt-3">
                              {event.note}
                            </p>
                          )}
                          {event.old_value && event.new_value && (
                            <div className="flex items-center gap-4 text-[10px] text-slate-400 mt-4 font-black uppercase tracking-widest bg-white p-3 rounded-xl border border-slate-100 inline-flex">
                              <span className="bg-rose-50 text-rose-600 px-2 py-1 rounded-lg">
                                {JSON.stringify(event.old_value)}
                              </span>
                              <ArrowRight className="w-3 h-3 text-slate-300" />
                              <span className="bg-shaheen-emerald/10 text-shaheen-emerald px-2 py-1 rounded-lg">
                                {JSON.stringify(event.new_value)}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-center py-20 bg-slate-50 rounded-[2.5rem] border-2 border-dashed border-slate-200">
                  <p className="text-slate-400 text-[10px] font-black uppercase tracking-widest">
                    Static Log - No further events detected
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    );
  }

  // List view
  return (
    <div className="space-y-10 max-w-[1400px] pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-4xl font-black text-[#002d5a] tracking-tighter">Mission Command</h1>
          <p className="text-slate-500 text-sm mt-2 font-bold uppercase tracking-widest flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-shaheen-emerald animate-pulse" />
            Active Service Intelligence Hub
          </p>
        </div>
        <button
          onClick={loadTickets}
          className="flex items-center justify-center gap-3 px-8 py-4 bg-[#002d5a] text-white rounded-2xl font-black uppercase tracking-widest hover:bg-[#003d7a] transition-all shadow-2xl shadow-[#002d5a]/20 text-xs"
        >
          <RefreshCw className="w-4 h-4" />
          Synchronize
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2 p-2 bg-white border border-slate-200 rounded-[2rem] shadow-xl">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className={`px-6 py-3 text-[10px] font-black uppercase tracking-widest rounded-2xl transition-all ${
              activeTab === tab.value
                ? "bg-[#002d5a] text-white shadow-xl"
                : "text-slate-400 hover:text-[#002d5a] hover:bg-slate-50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-4 p-6 bg-rose-50 border-l-4 border-rose-600 rounded-2xl shadow-lg">
          <AlertTriangle className="w-6 h-6 text-rose-600" />
          <p className="text-rose-700 text-sm font-black uppercase tracking-tight">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-32 gap-6">
          <div className="w-20 h-20 rounded-3xl bg-slate-50 flex items-center justify-center border border-slate-100">
            <RefreshCw className="w-10 h-10 text-[#002d5a] animate-spin" />
          </div>
          <p className="text-[#002d5a]/30 text-[10px] font-black uppercase tracking-[0.3em]">Querying Database...</p>
        </div>
      ) : tickets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 bg-white border border-slate-200 rounded-[3rem] shadow-2xl">
          <div className="w-24 h-24 rounded-[2rem] bg-slate-50 flex items-center justify-center mb-8 border border-slate-100">
            <Search className="w-10 h-10 text-slate-200" />
          </div>
          <p className="text-[#002d5a] text-xl font-black tracking-tight">No Missions Detected</p>
          <p className="text-slate-400 text-[10px] font-black uppercase tracking-widest mt-2">
            Initiate interactions via Support Command to generate logs
          </p>
        </div>
      ) : (
        /* Tickets Table */
        <div className="bg-white border border-slate-200 rounded-[3rem] overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] text-slate-400 uppercase tracking-[0.2em] bg-slate-50/50 border-b border-slate-200">
                  <th className="px-8 py-6 font-black">Mission Subject</th>
                  <th className="px-8 py-6 font-black text-center">Status</th>
                  <th className="px-8 py-6 font-black text-center">Priority</th>
                  <th className="px-8 py-6 font-black text-center">Channel</th>
                  <th className="px-8 py-6 font-black">Assignee</th>
                  <th className="px-8 py-6 font-black text-right">Initiated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    onClick={() => openDetail(ticket)}
                    className="hover:bg-slate-50/50 cursor-pointer transition-all group"
                  >
                    <td className="px-8 py-6">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-slate-50 group-hover:bg-[#002d5a] transition-all flex items-center justify-center flex-shrink-0 shadow-inner group-hover:shadow-lg">
                          <TicketIcon className="w-5 h-5 text-[#002d5a]/30 group-hover:text-white" />
                        </div>
                        <span className="font-black text-[#002d5a] group-hover:translate-x-1 transition-all max-w-sm truncate text-base tracking-tight">
                          {ticket.subject}
                        </span>
                      </div>
                    </td>
                    <td className="px-8 py-6 text-center">
                      <span
                        className={`inline-flex px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-full shadow-sm ${
                          STATUS_STYLES[ticket.status] ?? STATUS_STYLES.open
                        }`}
                      >
                        {ticket.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-8 py-6 text-center">
                      <span
                        className={`inline-flex items-center gap-2 px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-full ${
                          PRIORITY_STYLES[ticket.priority] ??
                          PRIORITY_STYLES.medium
                        }`}
                      >
                        <div
                          className={`w-1.5 h-1.5 rounded-full ${
                            PRIORITY_DOT[ticket.priority] ?? "bg-[#002d5a]"
                          }`}
                        />
                        {ticket.priority}
                      </span>
                    </td>
                    <td className="px-8 py-6 text-center">
                      <span className="inline-flex px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg bg-slate-100 text-slate-500 border border-slate-200">
                        {ticket.channel}
                      </span>
                    </td>
                    <td className="px-8 py-6 text-[#002d5a] font-black text-sm">
                      {ticket.assigned_to ?? (
                        <span className="italic text-slate-300 font-bold uppercase text-[10px]">
                          Unassigned
                        </span>
                      )}
                    </td>
                    <td className="px-8 py-6 text-slate-400 font-black text-right tabular-nums text-[11px]">
                      {new Date(ticket.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-8 py-5 border-t border-slate-100 bg-slate-50/30 flex justify-between items-center">
            <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest">
              Total Intelligence Units: {tickets.length}
            </p>
            <div className="flex gap-2">
               <div className="w-1.5 h-1.5 rounded-full bg-shaheen-emerald animate-pulse" />
               <div className="w-1.5 h-1.5 rounded-full bg-shaheen-emerald/40" />
               <div className="w-1.5 h-1.5 rounded-full bg-shaheen-emerald/20" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
