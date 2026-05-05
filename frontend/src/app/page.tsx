"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Users,
  MessagesSquare,
  Ticket,
  MessageSquare,
  RefreshCw,
  Database,
  TrendingUp,
  Clock,
  AlertTriangle,
  Plane,
  ArrowUpRight,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { getDemoStats, getDashboardMetrics, seedDemoData } from "@/lib/api";
import type { DBStats, DashboardMetrics } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  open: "#0284c7",
  in_progress: "#d97706",
  escalated: "#dc2626",
  resolved: "#16a34a",
  closed: "#64748b",
  waiting_on_customer: "#7c3aed",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  escalated: "Escalated",
  resolved: "Resolved",
  closed: "Closed",
  waiting_on_customer: "Waiting",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DBStats | null>(null);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, m] = await Promise.all([
        getDemoStats(),
        getDashboardMetrics().catch(() => null),
      ]);
      setStats(s);
      setMetrics(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await seedDemoData();
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to seed data");
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-sky-100 to-blue-50 flex items-center justify-center">
            <Plane className="w-8 h-8 text-accent animate-pulse" />
          </div>
          <p className="text-muted-foreground text-sm font-medium">
            Loading dashboard...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-5">
        <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center">
          <AlertTriangle className="w-8 h-8 text-danger" />
        </div>
        <div className="text-center">
          <p className="text-danger text-lg font-semibold">Connection Error</p>
          <p className="text-muted-foreground text-sm mt-1 max-w-md">
            Unable to reach the backend server. Make sure the API is running on
            localhost:8000
          </p>
        </div>
        <button
          onClick={loadData}
          className="px-6 py-2.5 bg-accent text-white rounded-xl font-medium hover:bg-accent-light transition-colors shadow-sm"
        >
          Try Again
        </button>
      </div>
    );
  }

  const statCards = [
    {
      label: "Total Customers",
      value: stats?.total_customers ?? 0,
      icon: Users,
      gradient: "from-sky-500 to-blue-600",
      bg: "bg-sky-50",
      iconColor: "text-sky-600",
    },
    {
      label: "Conversations",
      value: stats?.total_conversations ?? 0,
      icon: MessagesSquare,
      gradient: "from-violet-500 to-purple-600",
      bg: "bg-violet-50",
      iconColor: "text-violet-600",
    },
    {
      label: "Messages",
      value: stats?.total_messages ?? 0,
      icon: MessageSquare,
      gradient: "from-emerald-500 to-green-600",
      bg: "bg-emerald-50",
      iconColor: "text-emerald-600",
    },
    {
      label: "Active Tickets",
      value: stats?.total_tickets ?? 0,
      icon: Ticket,
      gradient: "from-amber-500 to-orange-600",
      bg: "bg-amber-50",
      iconColor: "text-amber-600",
    },
  ];

  const pieData = Object.entries(stats?.tickets_by_status ?? {})
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-8 max-w-[1400px]">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#0c4a6e] to-[#1e3a5f] p-8 shadow-xl">
        <div className="absolute top-0 right-0 w-80 h-80 opacity-10">
          <Plane className="w-full h-full text-white" />
        </div>
        <div className="relative flex items-center justify-between">
          <div>
            <p className="text-sky-300 text-sm font-medium tracking-wide uppercase mb-1">
              Command Center
            </p>
            <h1 className="text-3xl font-bold text-white">
              Shaheen Airline Dashboard
            </h1>
            <p className="text-sky-200/70 text-sm mt-2 max-w-lg">
              Real-time overview of customer support operations, AI performance
              metrics, and service analytics
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleSeed}
              disabled={seeding}
              className="flex items-center gap-2 px-5 py-2.5 bg-white/10 backdrop-blur-sm border border-white/20 text-white rounded-xl hover:bg-white/20 transition-all disabled:opacity-50 text-sm font-medium"
            >
              <Database className="w-4 h-4" />
              {seeding ? "Seeding..." : "Seed Data"}
            </button>
            <button
              onClick={loadData}
              className="flex items-center gap-2 px-5 py-2.5 bg-amber-500 text-white rounded-xl hover:bg-amber-400 transition-all shadow-lg shadow-amber-500/25 text-sm font-medium"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="animate-fade-in-up bg-card border border-border rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow"
              style={{ animationDelay: `${idx * 80}ms` }}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {card.label}
                  </p>
                  <p className="text-3xl font-bold mt-2 text-foreground">
                    {card.value.toLocaleString()}
                  </p>
                </div>
                <div
                  className={`w-12 h-12 rounded-xl ${card.bg} flex items-center justify-center`}
                >
                  <Icon className={`w-6 h-6 ${card.iconColor}`} />
                </div>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                <ArrowUpRight className="w-3.5 h-3.5 text-success" />
                <span className="text-success font-medium">Active</span>
                <span>this period</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Donut Chart */}
        <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-foreground">
              Ticket Distribution
            </h2>
            <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full">
              By Status
            </span>
          </div>
          {pieData.length > 0 ? (
            <>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      dataKey="value"
                      stroke="#fff"
                      strokeWidth={3}
                    >
                      {pieData.map((entry) => (
                        <Cell
                          key={entry.name}
                          fill={STATUS_COLORS[entry.name] ?? "#64748b"}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "#ffffff",
                        border: "1px solid #e2e8f0",
                        borderRadius: "12px",
                        color: "#0f172a",
                        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                        fontSize: "13px",
                        padding: "8px 14px",
                      }}
                      formatter={(value, name) => [
                        String(value),
                        STATUS_LABELS[name as string] ?? String(name),
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-3">
                {pieData.map((entry) => (
                  <div
                    key={entry.name}
                    className="flex items-center gap-2.5 text-xs px-2 py-1.5 rounded-lg hover:bg-muted/50 transition"
                  >
                    <div
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{
                        background: STATUS_COLORS[entry.name] ?? "#64748b",
                      }}
                    />
                    <span className="text-muted-foreground">
                      {STATUS_LABELS[entry.name] ?? entry.name}
                    </span>
                    <span className="font-semibold text-foreground ml-auto">
                      {entry.value}
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-3">
                <Ticket className="w-7 h-7 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground text-sm">No ticket data yet</p>
              <p className="text-muted-foreground/60 text-xs mt-1">
                Click &quot;Seed Data&quot; to populate
              </p>
            </div>
          )}
        </div>

        {/* Performance Metrics */}
        <div className="bg-card border border-border rounded-2xl p-6 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-foreground">
              AI Performance
            </h2>
            <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full">
              Real-time
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <MetricCard
              icon={TrendingUp}
              label="AI Resolution Rate"
              value={
                metrics?.resolution
                  ? `${metrics.resolution.ai_resolution_rate_pct.toFixed(1)}%`
                  : "N/A"
              }
              detail={
                metrics?.resolution
                  ? `${metrics.resolution.resolved_by_ai} of ${metrics.resolution.total_runs} resolved by AI`
                  : "Awaiting data"
              }
              color="text-emerald-600"
              bg="bg-emerald-50"
            />
            <MetricCard
              icon={Clock}
              label="Avg Response Time"
              value={
                metrics?.response_time
                  ? `${(metrics.response_time.avg_ms / 1000).toFixed(1)}s`
                  : stats?.avg_response_time_ms
                  ? `${(stats.avg_response_time_ms / 1000).toFixed(1)}s`
                  : "N/A"
              }
              detail={
                metrics?.response_time
                  ? `P95: ${(metrics.response_time.p95_ms / 1000).toFixed(1)}s latency`
                  : "Awaiting data"
              }
              color="text-sky-600"
              bg="bg-sky-50"
            />
            <MetricCard
              icon={AlertTriangle}
              label="Escalation Rate"
              value={
                metrics?.escalations
                  ? `${metrics.escalations.escalation_rate_pct.toFixed(1)}%`
                  : stats
                  ? `${stats.escalated_tickets}`
                  : "N/A"
              }
              detail={
                metrics?.escalations
                  ? `${metrics.escalations.escalated_count} of ${metrics.escalations.total_runs} escalated`
                  : "Escalated tickets"
              }
              color="text-amber-600"
              bg="bg-amber-50"
            />
          </div>
        </div>
      </div>

      {/* Recent Messages */}
      <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">
              Recent Messages
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Latest customer interactions
            </p>
          </div>
          <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full">
            {stats?.recent_messages?.length ?? 0} messages
          </span>
        </div>
        {stats?.recent_messages && stats.recent_messages.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground uppercase tracking-wider bg-muted/30">
                  <th className="px-6 py-3 font-semibold">Direction</th>
                  <th className="px-6 py-3 font-semibold">Sender</th>
                  <th className="px-6 py-3 font-semibold">Channel</th>
                  <th className="px-6 py-3 font-semibold">Content</th>
                  <th className="px-6 py-3 font-semibold">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {stats.recent_messages.map((msg) => (
                  <tr
                    key={msg.id}
                    className="hover:bg-muted/20 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-lg ${
                          msg.direction === "inbound"
                            ? "bg-sky-50 text-sky-700 ring-1 ring-sky-200"
                            : "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                        }`}
                      >
                        {msg.direction === "inbound" ? "Inbound" : "Outbound"}
                      </span>
                    </td>
                    <td className="px-6 py-4 capitalize font-medium text-foreground">
                      {msg.sender}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-lg bg-muted text-muted-foreground capitalize">
                        {msg.channel}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-w-sm truncate text-muted-foreground">
                      {msg.content}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground whitespace-nowrap text-xs">
                      {new Date(msg.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-3">
              <MessageSquare className="w-7 h-7 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground text-sm font-medium">
              No messages yet
            </p>
            <p className="text-muted-foreground/60 text-xs mt-1">
              Submit a message from Live Support or seed demo data
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  color,
  bg,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
  color: string;
  bg: string;
}) {
  return (
    <div className="rounded-xl border border-border p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center`}
        >
          <Icon className={`w-5 h-5 ${color}`} />
        </div>
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      <p className="text-xs text-muted-foreground mt-1.5">{detail}</p>
    </div>
  );
}
