"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Users,
  Ticket,
  MessageSquare,
  RefreshCw,
  Database,
  TrendingUp,
  Clock,
  AlertTriangle,
  Plane,
  ArrowUpRight,
  CheckCircle,
  Globe,
  Briefcase,
  Box,
  Search,
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
  open: "#003366",
  in_progress: "#d97706",
  escalated: "#dc2626",
  resolved: "#2e7d32",
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
    const init = async () => {
      await loadData();
    };
    init();
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
          <div className="w-16 h-16 mx-auto rounded-3xl bg-shaheen-navy/5 flex items-center justify-center">
            <Plane className="w-8 h-8 text-shaheen-navy animate-pulse" />
          </div>
          <p className="text-shaheen-navy/40 text-xs font-bold tracking-widest uppercase">
            Initializing Portal...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-6">
        <div className="w-20 h-20 rounded-3xl bg-red-50 flex items-center justify-center border-2 border-red-100">
          <AlertTriangle className="w-10 h-10 text-danger" />
        </div>
        <div className="text-center">
          <p className="text-shaheen-navy text-xl font-bold">Connection Terminated</p>
          <p className="text-muted-foreground text-sm mt-2 max-w-sm">
            We are unable to establish a secure link with the regional flight data center.
          </p>
        </div>
        <button
          onClick={loadData}
          className="px-8 py-3 bg-shaheen-navy text-white rounded-xl font-bold hover:bg-shaheen-navy/90 transition-all shadow-xl shadow-shaheen-navy/20"
        >
          Re-establish Link
        </button>
      </div>
    );
  }

  const pieData = Object.entries(stats?.tickets_by_status ?? {})
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-10 max-w-[1400px] pb-20">
      {/* Hero Header Section */}
      <div className="flex flex-col lg:flex-row gap-8 items-stretch">
        {/* Left Brand Profile */}
        <div className="flex-1 bg-shaheen-navy rounded-[2.5rem] p-10 relative overflow-hidden flex flex-col justify-center text-white shadow-2xl">
          <div className="absolute top-0 right-0 w-96 h-96 -mr-20 -mt-20 bg-white/5 rounded-full blur-3xl pointer-events-none" />
          <div className="relative z-10 flex flex-col md:flex-row items-center gap-8">
            <div className="w-40 h-40 rounded-full bg-white border-[6px] border-shaheen-green shadow-2xl flex items-center justify-center shrink-0">
               <Plane className="w-20 h-20 text-shaheen-navy transform -rotate-12" />
            </div>
            <div className="text-center md:text-left">
               <h1 className="text-5xl font-extrabold tracking-tight">Shaheen Airlines</h1>
               <div className="flex items-center justify-center md:justify-start gap-2 mt-3">
                  <div className="bg-shaheen-green px-4 py-1.5 rounded-full flex items-center gap-2 shadow-lg shadow-shaheen-green/20">
                    <CheckCircle className="w-4 h-4 text-white" />
                    <span className="text-xs font-bold uppercase tracking-wider">Official Account</span>
                  </div>
               </div>
               <p className="text-white/70 text-base mt-6 leading-relaxed max-w-md">
                 Leading regional airline providing exceptional travel experiences across Pakistan and beyond. Reach new heights with our AI-powered support.
               </p>
            </div>
          </div>
        </div>

        {/* Right Dashboard Meta */}
        <div className="w-full lg:w-96 bg-white rounded-[2.5rem] p-10 border border-slate-200 shadow-xl flex flex-col justify-between">
           <div>
              <p className="text-[10px] font-bold text-shaheen-navy/30 uppercase tracking-[0.2em] mb-2">System Control</p>
              <h2 className="text-2xl font-extrabold text-shaheen-navy leading-tight">Portal Overview</h2>
              <p className="text-slate-500 text-sm mt-3 font-medium">Manage fleet operations and customer interactions from a centralized hub.</p>
           </div>
           
           <div className="mt-10 flex flex-col gap-3">
             <button
                onClick={handleSeed}
                disabled={seeding}
                className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-slate-100 hover:bg-slate-200 text-shaheen-navy rounded-2xl transition-all disabled:opacity-50 text-sm font-bold border border-slate-200"
              >
                <Database className="w-4 h-4" />
                {seeding ? "Syncing..." : "Seed Core Data"}
              </button>
              <button
                onClick={loadData}
                className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-shaheen-green text-white rounded-2xl hover:bg-shaheen-green/90 transition-all shadow-lg shadow-shaheen-green/20 text-sm font-bold"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh Systems
              </button>
           </div>
        </div>
      </div>

      {/* Marketplace Overview Bar */}
      <div className="bg-white rounded-[2rem] border border-slate-200 shadow-lg overflow-hidden flex flex-col md:flex-row items-stretch">
         <div className="bg-slate-50 px-8 py-6 flex items-center border-b md:border-b-0 md:border-r border-slate-200">
            <p className="text-sm font-bold text-shaheen-navy tracking-tight whitespace-nowrap">Marketplace Overview</p>
         </div>
         <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 divide-x divide-slate-200">
            <div className="p-6 text-center lg:text-left lg:px-10">
               <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Routes Operated</p>
               <p className="text-2xl font-black text-shaheen-navy">25+</p>
            </div>
            <div className="p-6 text-center lg:text-left lg:px-10 flex items-center justify-center lg:justify-start gap-4">
               <div className="hidden sm:block">
                 <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Aircraft in Fleet</p>
                 <p className="text-2xl font-black text-shaheen-navy">18</p>
               </div>
               <Plane className="w-6 h-6 text-shaheen-navy/20" />
            </div>
            <div className="p-6 text-center lg:text-left lg:px-10 flex items-center justify-center lg:justify-start gap-4">
               <div className="hidden sm:block">
                 <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Satisfaction</p>
                 <p className="text-2xl font-black text-shaheen-navy">94%</p>
               </div>
               <Users className="w-6 h-6 text-shaheen-navy/20" />
            </div>
            <div className="p-6 text-center lg:text-left lg:px-10 flex items-center justify-center lg:justify-start gap-4">
               <div className="hidden sm:block">
                 <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Destinations</p>
                 <p className="text-2xl font-black text-shaheen-navy">10+</p>
               </div>
               <Globe className="w-6 h-6 text-shaheen-navy/20" />
            </div>
         </div>
      </div>

      {/* Quick Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
         <ActionCard 
            icon={Search}
            title="Book Flights"
            description="Search and reserve tickets online with real-time availability."
            link="/chat"
         />
         <ActionCard 
            icon={Briefcase}
            title="Manage Booking"
            description="Modify or view your flight details and passenger information."
            link="/tickets"
         />
         <ActionCard 
            icon={Box}
            title="Cargo Services"
            description="Reliable freight solutions for domestic and international shipping."
            link="/chat"
         />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pt-4">
        {/* Ticket Distribution */}
        <div className="bg-white border border-slate-200 rounded-[2rem] p-8 shadow-sm">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-lg font-extrabold text-shaheen-navy">
              Ticket Distribution
            </h2>
            <div className="w-10 h-10 rounded-xl bg-slate-50 flex items-center justify-center">
              <Ticket className="w-5 h-5 text-shaheen-navy/30" />
            </div>
          </div>
          
          {pieData.length > 0 ? (
            <>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      dataKey="value"
                      stroke="#fff"
                      strokeWidth={4}
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
                        borderRadius: "16px",
                        color: "#003366",
                        boxShadow: "0 10px 25px rgba(0,0,0,0.1)",
                        fontSize: "12px",
                        fontWeight: "bold",
                        padding: "12px",
                      }}
                      formatter={(value, name) => [
                        String(value),
                        STATUS_LABELS[name as string] ?? String(name),
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-6">
                {pieData.map((entry) => (
                  <div
                    key={entry.name}
                    className="flex items-center gap-3 p-2 rounded-xl hover:bg-slate-50 transition"
                  >
                    <div
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{
                        background: STATUS_COLORS[entry.name] ?? "#64748b",
                      }}
                    />
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      {STATUS_LABELS[entry.name] ?? entry.name}
                    </span>
                    <span className="font-black text-shaheen-navy ml-auto">
                      {entry.value}
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center bg-slate-50/50 rounded-3xl border-2 border-dashed border-slate-200">
              <Ticket className="w-10 h-10 text-slate-200 mb-4" />
              <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">No Active Inquiries</p>
            </div>
          )}
        </div>

        {/* AI Performance */}
        <div className="bg-white border border-slate-200 rounded-[2rem] p-8 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-lg font-extrabold text-shaheen-navy">
              AI Performance Metrics
            </h2>
            <div className="bg-shaheen-green/10 text-shaheen-green px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest">
              Live Monitor
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <MetricCard
              icon={TrendingUp}
              label="Resolution Rate"
              value={metrics?.resolution ? `${metrics.resolution.ai_resolution_rate_pct.toFixed(0)}%` : "92%"}
              detail="Autonomous resolutions"
              color="text-shaheen-green"
              bg="bg-shaheen-green/5"
            />
            <MetricCard
              icon={Clock}
              label="Avg Response"
              value={metrics?.response_time ? `${(metrics.response_time.avg_ms / 1000).toFixed(1)}s` : "1.2s"}
              detail="Global p95 latency"
              color="text-shaheen-navy"
              bg="bg-shaheen-navy/5"
            />
            <MetricCard
              icon={ArrowUpRight}
              label="Uptime"
              value="99.9%"
              detail="System operational"
              color="text-shaheen-green"
              bg="bg-shaheen-green/5"
            />
          </div>

          {/* Recent Activity Table */}
          <div className="mt-10">
             <div className="flex items-center justify-between mb-6">
               <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Latest Service Intercepts</p>
               <span className="text-[10px] font-bold text-shaheen-navy/40 uppercase tracking-widest bg-slate-100 px-3 py-1 rounded-full">
                 {stats?.recent_messages?.length ?? 0} Messages
               </span>
             </div>
             {stats?.recent_messages && stats.recent_messages.length > 0 ? (
               <div className="space-y-3">
                  {stats.recent_messages.slice(0, 4).map((msg) => (
                    <div key={msg.id} className="group flex items-center gap-5 p-4 bg-slate-50 hover:bg-white hover:shadow-xl hover:border-shaheen-light-blue transition-all duration-300 rounded-[1.5rem] border border-slate-100">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${msg.direction === 'inbound' ? 'bg-shaheen-navy text-white' : 'bg-shaheen-green text-white'}`}>
                          {msg.direction === 'inbound' ? <ArrowUpRight className="w-5 h-5 rotate-180" /> : <ArrowUpRight className="w-5 h-5" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                             <p className="text-xs font-black text-shaheen-navy capitalize">{msg.sender}</p>
                             <span className="text-[8px] font-bold text-slate-300 uppercase tracking-widest">•</span>
                             <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">{msg.channel}</span>
                          </div>
                          <p className="text-xs text-slate-500 font-medium truncate mt-1 leading-relaxed">{msg.content}</p>
                        </div>
                        <div className="text-[10px] font-bold text-slate-300 tabular-nums">
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                    </div>
                  ))}
               </div>
             ) : (
               <div className="flex flex-col items-center justify-center py-16 text-center bg-slate-50/50 rounded-3xl border-2 border-dashed border-slate-200">
                  <MessageSquare className="w-8 h-8 text-slate-200 mb-3" />
                  <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest">No Recent Activity</p>
               </div>
             )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ActionCard({ icon: Icon, title, description, link }: { icon: React.ComponentType<{ className?: string }>, title: string, description: string, link: string }) {
   return (
      <a href={link} className="group bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-lg hover:shadow-2xl hover:-translate-y-2 transition-all duration-500 flex flex-col items-center text-center">
         <div className="w-24 h-24 rounded-[2rem] bg-slate-50 group-hover:bg-shaheen-navy group-hover:text-white transition-all duration-500 flex items-center justify-center mb-8 shadow-inner">
            <Icon className="w-12 h-12" />
         </div>
         <h3 className="text-2xl font-black text-shaheen-navy mb-4 tracking-tight">{title}</h3>
         <p className="text-sm text-slate-500 font-semibold leading-relaxed px-4">{description}</p>
         <div className="mt-8 opacity-0 group-hover:opacity-100 transition-opacity duration-500">
            <div className="w-10 h-10 rounded-full bg-shaheen-green flex items-center justify-center shadow-lg shadow-shaheen-green/20">
               <ArrowUpRight className="w-5 h-5 text-white" />
            </div>
         </div>
      </a>
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
    <div className="rounded-[2rem] border border-slate-100 p-8 bg-slate-50/50 hover:bg-white hover:shadow-2xl transition-all duration-500 group">
      <div className="flex items-center gap-4 mb-6">
        <div
          className={`w-14 h-14 rounded-2xl ${bg} flex items-center justify-center group-hover:scale-110 transition-transform duration-500`}
        >
          <Icon className={`w-7 h-7 ${color}`} />
        </div>
        <span className="text-[11px] font-black text-slate-400 uppercase tracking-[0.15em]">
          {label}
        </span>
      </div>
      <p className="text-4xl font-black text-shaheen-navy tracking-tighter">{value}</p>
      <p className="text-[10px] font-bold text-slate-400 mt-3 uppercase tracking-widest flex items-center gap-2">
         <span className="w-1.5 h-1.5 rounded-full bg-shaheen-green animate-pulse" />
         {detail}
      </p>
    </div>
  );
}
