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
  MapPin,
  Shield,
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
    <div className="space-y-16 pb-24 -mt-12 lg:-mt-12">
      {/* Marketplace Hero & Search Section */}
      <section className="relative h-[600px] w-[calc(100%+64px)] lg:w-[calc(100%+96px)] -ml-8 lg:-ml-12 overflow-hidden bg-[#002d5a]">
         <div className="absolute inset-0 bg-gradient-to-r from-[#002d5a] via-[#002d5a]/90 to-transparent z-10" />
         <div className="absolute inset-0 opacity-20 z-0">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-shaheen-emerald/20 via-transparent to-transparent blur-3xl" />
         </div>

         <div className="relative z-20 h-full flex flex-col justify-center px-10 lg:px-24">
            <div className="max-w-3xl">
               <div className="bg-shaheen-emerald/20 text-shaheen-emerald px-4 py-1.5 rounded-full inline-flex items-center gap-2 mb-8 border border-shaheen-emerald/30">
                  <Plane className="w-4 h-4" />
                  <span className="text-[10px] font-black uppercase tracking-[0.25em]">Official Regional Marketplace</span>
               </div>
               <h1 className="text-7xl font-black text-white tracking-tighter leading-[1.1] mb-6">
                  Reach New <span className="text-shaheen-emerald">Heights</span><br />
                  With Every Mission.
               </h1>
               <p className="text-white/60 text-xl font-medium leading-relaxed max-w-xl">
                  Coordinate fleet logistics, book regional flight vectors, and manage mission-critical support from the official Shaheen Airlines terminal.
               </p>
            </div>

            {/* Marketplace Search Bar */}
            <div className="mt-16 max-w-5xl">
               <div className="bg-white p-2 rounded-[2.5rem] shadow-2xl flex flex-col md:flex-row items-stretch gap-2 border-4 border-white/10 backdrop-blur-xl">
                  <div className="flex-1 flex items-center gap-4 px-8 py-4 bg-slate-50 rounded-[1.5rem] border border-slate-100 group focus-within:ring-2 focus-within:ring-[#002d5a]/20 transition-all">
                     <Search className="w-5 h-5 text-slate-300 group-focus-within:text-[#002d5a]" />
                     <input 
                        type="text" 
                        placeholder="Search Missions, Flight Vectors, or Service Logs..." 
                        className="bg-transparent border-none outline-none w-full text-sm font-bold text-[#002d5a] placeholder:text-slate-400"
                     />
                  </div>
                  <div className="flex items-center gap-4 px-8 py-4 bg-slate-50 rounded-[1.5rem] border border-slate-100 min-w-[200px]">
                     <MapPin className="w-5 h-5 text-slate-300" />
                     <span className="text-sm font-bold text-[#002d5a]">Global Network</span>
                  </div>
                  <button className="bg-[#002d5a] text-white px-10 py-5 rounded-[1.5rem] font-black uppercase tracking-widest text-xs hover:bg-[#003d7a] transition-all shadow-xl shadow-[#002d5a]/30">
                     Execute Query
                  </button>
               </div>
            </div>
         </div>
      </section>

      {/* Trust & Metric Bar */}
      <section className="bg-white rounded-[2.5rem] border border-slate-200 shadow-2xl p-1 overflow-hidden">
         <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-slate-100">
            {[
               { label: "Active Vectors", value: "25+", icon: Plane },
               { label: "Fleet Readiness", value: "100%", icon: Shield },
               { label: "Mission Satisfaction", value: "94%", icon: Users },
               { label: "Global Presence", value: "10+", icon: Globe }
            ].map((stat) => (
               <div key={stat.label} className="px-10 py-10 flex items-center justify-between group hover:bg-slate-50 transition-colors">
                  <div>
                     <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">{stat.label}</p>
                     <p className="text-4xl font-black text-[#002d5a] tracking-tighter">{stat.value}</p>
                  </div>
                  <stat.icon className="w-10 h-10 text-slate-100 group-hover:text-shaheen-emerald/20 transition-colors" />
               </div>
            ))}
         </div>
      </section>

      {/* Marketplace Segments */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-12 pt-8">
         <ActionCard 
            icon={Search}
            title="Vector Booking"
            description="Execute real-time flight searches and secure reservations through our global regional network."
            link="/chat"
         />
         <ActionCard 
            icon={Briefcase}
            title="Manifest Management"
            description="Access and modify passenger manifests and flight itinerary details with total oversight."
            link="/tickets"
         />
         <ActionCard 
            icon={Box}
            title="Logistics Command"
            description="Coordinate mission-critical logistics for domestic and international freight operations."
            link="/chat"
         />
      </section>

      {/* Intelligence & Telemetry */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-12 pt-8">
         <div className="bg-white border border-slate-200 rounded-[3rem] p-12 shadow-2xl">
            <h2 className="text-2xl font-black text-[#002d5a] tracking-tight mb-8">Mission Status</h2>
            <div className="space-y-6">
               {[
                  { label: "Open Missions", value: stats?.total_tickets ?? 0, color: "bg-[#002d5a]" },
                  { label: "Resolved Vectors", value: "852", color: "bg-shaheen-emerald" },
                  { label: "Active Intel", value: stats?.total_messages ?? 0, color: "bg-amber-500" }
               ].map((item) => (
                  <div key={item.label} className="p-6 rounded-[1.5rem] bg-slate-50 border border-slate-100 flex items-center justify-between group hover:shadow-xl transition-all">
                     <div className="flex items-center gap-4">
                        <div className={`w-3 h-3 rounded-full ${item.color} shadow-lg`} />
                        <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest">{item.label}</span>
                     </div>
                     <span className="text-2xl font-black text-[#002d5a]">{item.value}</span>
                  </div>
               ))}
            </div>
            
            <div className="mt-12">
               <button 
                  onClick={handleSeed}
                  className="w-full py-5 rounded-[1.5rem] bg-slate-100 text-[10px] font-black uppercase tracking-widest text-[#002d5a] border border-slate-200 hover:bg-slate-200 transition-all"
               >
                  Sync Core Systems
               </button>
            </div>
         </div>

         <div className="bg-white border border-slate-200 rounded-[3rem] p-12 shadow-2xl lg:col-span-2 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-80 h-80 bg-shaheen-emerald/5 rounded-full -mr-40 -mt-40 blur-3xl" />
            
            <div className="relative z-10">
               <div className="flex items-center justify-between mb-12">
                  <h2 className="text-2xl font-black text-[#002d5a] tracking-tight">AI Command Telemetry</h2>
                  <div className="bg-shaheen-emerald/10 text-shaheen-emerald px-6 py-2 rounded-full text-[10px] font-black uppercase tracking-[0.2em] border border-shaheen-emerald/20">
                     Active Link
                  </div>
               </div>
               
               <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                  <MetricCard
                     icon={TrendingUp}
                     label="Autonomous"
                     value={metrics?.resolution ? `${metrics.resolution.ai_resolution_rate_pct.toFixed(0)}%` : "92%"}
                     detail="Success Rate"
                     color="text-shaheen-emerald"
                     bg="bg-shaheen-emerald/5"
                  />
                  <MetricCard
                     icon={Clock}
                     label="Latency"
                     value={metrics?.response_time ? `${(metrics.response_time.avg_ms / 1000).toFixed(1)}s` : "1.2s"}
                     detail="Response Time"
                     color="text-[#002d5a]"
                     bg="bg-[#002d5a]/5"
                  />
                  <MetricCard
                     icon={ArrowUpRight}
                     label="Health"
                     value="100%"
                     detail="Operational"
                     color="text-shaheen-emerald"
                     bg="bg-shaheen-emerald/5"
                  />
               </div>

               <div className="mt-12 bg-slate-50 rounded-[2rem] p-8 border border-slate-100">
                  <div className="flex items-center justify-between mb-8">
                     <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Recent Mission Logs</p>
                     <button onClick={loadData} className="text-shaheen-emerald hover:rotate-180 transition-transform duration-500">
                        <RefreshCw className="w-4 h-4" />
                     </button>
                  </div>
                  <div className="space-y-4">
                     {stats?.recent_messages?.slice(0, 3).map((msg) => (
                        <div key={msg.id} className="flex items-center gap-6 bg-white p-4 rounded-2xl border border-slate-100 shadow-sm">
                           <div className={`w-2 h-10 rounded-full ${msg.direction === 'inbound' ? 'bg-[#002d5a]' : 'bg-shaheen-emerald'}`} />
                           <div className="flex-1 min-w-0">
                              <p className="text-xs font-black text-[#002d5a] capitalize">{msg.sender}</p>
                              <p className="text-[11px] text-slate-400 font-medium truncate">{msg.content}</p>
                           </div>
                           <span className="text-[9px] font-black text-slate-300 uppercase">{msg.channel}</span>
                        </div>
                     ))}
                  </div>
               </div>
            </div>
         </div>
      </section>
    </div>
  );
}

function ActionCard({ icon: Icon, title, description, link }: { icon: React.ComponentType<{ className?: string }>, title: string, description: string, link: string }) {
   return (
      <a href={link} className="group bg-white p-12 rounded-[3.5rem] border border-slate-200 shadow-xl hover:shadow-[0_40px_80px_rgba(0,45,90,0.15)] hover:-translate-y-3 transition-all duration-700 flex flex-col items-center text-center relative overflow-hidden">
         <div className="absolute top-0 right-0 w-32 h-32 bg-slate-50 rounded-bl-[5rem] -mr-16 -mt-16 transition-all duration-700 group-hover:bg-[#002d5a]/5" />
         <div className="w-28 h-28 rounded-[2.5rem] bg-slate-50 group-hover:bg-[#002d5a] group-hover:text-white transition-all duration-700 flex items-center justify-center mb-10 shadow-inner group-hover:shadow-2xl">
            <Icon className="w-14 h-14" />
         </div>
         <h3 className="text-3xl font-black text-[#002d5a] mb-5 tracking-tighter leading-none">{title}</h3>
         <p className="text-base text-slate-500 font-bold leading-relaxed px-6">{description}</p>
         <div className="mt-10 opacity-0 group-hover:opacity-100 transition-all duration-700 transform translate-y-4 group-hover:translate-y-0">
            <div className="px-6 py-2 rounded-full bg-shaheen-emerald text-white text-[10px] font-black uppercase tracking-widest shadow-xl shadow-shaheen-emerald/30 flex items-center gap-2">
               Execute <ArrowUpRight className="w-4 h-4" />
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
    <div className="rounded-[2.5rem] border border-slate-100 p-10 bg-slate-50/50 hover:bg-white hover:shadow-[0_30px_60px_rgba(0,0,0,0.08)] transition-all duration-700 group border-b-4 hover:border-b-shaheen-emerald">
      <div className="flex items-center gap-5 mb-8">
        <div
          className={`w-16 h-16 rounded-[1.5rem] ${bg} flex items-center justify-center group-hover:scale-110 transition-transform duration-700 shadow-inner`}
        >
          <Icon className={`w-8 h-8 ${color}`} />
        </div>
        <span className="text-[12px] font-black text-slate-400 uppercase tracking-[0.2em]">
          {label}
        </span>
      </div>
      <p className="text-5xl font-black text-[#002d5a] tracking-tighter">{value}</p>
      <p className="text-[11px] font-black text-slate-400 mt-5 uppercase tracking-widest flex items-center gap-3">
         <span className="w-2 h-2 rounded-full bg-shaheen-emerald animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
         {detail}
      </p>
    </div>
  );
}
