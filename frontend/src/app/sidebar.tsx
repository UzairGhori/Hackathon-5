"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Ticket,
  MessageSquare,
  Plane,
  Headphones,
  Shield,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, desc: "Overview & Analytics" },
  { href: "/tickets", label: "Tickets", icon: Ticket, desc: "Support Requests" },
  { href: "/chat", label: "Live Support", icon: MessageSquare, desc: "AI Assistant" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-72 bg-[#002d5a] flex flex-col z-50 shadow-2xl border-r border-white/5">
      {/* Brand Header */}
      <div className="p-8 pb-8">
        <div className="flex flex-col gap-5">
          <div className="w-16 h-16 rounded-2xl bg-white flex items-center justify-center shadow-2xl border-2 border-shaheen-emerald">
            <Plane className="w-10 h-10 text-[#002d5a]" />
          </div>
          <div>
            <h1 className="font-black text-2xl text-white tracking-tighter leading-none">
              SHAHEEN
            </h1>
            <p className="text-[10px] text-shaheen-emerald font-black tracking-[0.3em] uppercase mt-1">
              AIRLINES
            </p>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-8 h-px bg-white/5" />

      {/* Navigation */}
      <nav className="flex-1 px-4 py-8 space-y-2.5">
        <p className="px-4 mb-5 text-[10px] font-black text-white/30 uppercase tracking-[0.25em]">
          Support Command
        </p>
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center gap-4 px-4 py-4 rounded-xl text-sm font-bold transition-all duration-300 ${
                isActive
                  ? "bg-white text-[#002d5a] shadow-2xl"
                  : "text-white/60 hover:text-white hover:bg-white/5"
              }`}
            >
              <div
                className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-300 ${
                  isActive
                    ? "bg-[#002d5a]/10 text-[#002d5a]"
                    : "bg-white/5 text-white/20 group-hover:bg-white/10 group-hover:text-white"
                }`}
              >
                <Icon className="w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <span className="leading-tight tracking-tight">{item.label}</span>
                <span
                  className={`text-[9px] font-bold uppercase tracking-wider mt-0.5 ${
                    isActive ? "text-[#002d5a]/40" : "text-white/20"
                  }`}
                >
                  {item.desc}
                </span>
              </div>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-shaheen-emerald shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Section */}
      <div className="p-6 bg-black/40">
        {/* Status Card */}
        <div className="px-4 py-4 bg-white/5 rounded-2xl border border-white/10 backdrop-blur-xl">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-shaheen-emerald/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-shaheen-emerald" />
            </div>
            <div>
              <p className="text-[11px] font-black text-white uppercase tracking-wider">Secure Portal</p>
              <p className="text-[9px] text-shaheen-emerald font-black uppercase tracking-widest mt-0.5">Verified Link</p>
            </div>
          </div>
        </div>

        {/* Support Line */}
        <div className="mt-4 flex items-center justify-center gap-2 text-white/40">
          <Headphones className="w-3.5 h-3.5" />
          <span className="text-[10px] font-bold tracking-wider uppercase">Support: Reach New Heights</span>
        </div>
      </div>
    </aside>
  );
}
