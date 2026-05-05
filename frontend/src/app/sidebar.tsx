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
    <aside className="fixed left-0 top-0 h-screen w-72 bg-gradient-to-b from-[#0c4a6e] to-[#0f172a] flex flex-col z-50 shadow-2xl">
      {/* Brand Header */}
      <div className="p-6 pb-5">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20 flex items-center justify-center shadow-lg">
            <Plane className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <h1 className="font-bold text-base text-white tracking-wide">
              Shaheen Airline
            </h1>
            <p className="text-[11px] text-sky-300/80 font-medium tracking-wider uppercase">
              Support Portal
            </p>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-5 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1.5">
        <p className="px-4 mb-3 text-[10px] font-semibold text-sky-400/60 uppercase tracking-[0.15em]">
          Main Menu
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
              className={`group flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? "bg-white/15 text-white shadow-lg shadow-black/10 backdrop-blur-sm border border-white/10"
                  : "text-sky-200/70 hover:text-white hover:bg-white/8"
              }`}
            >
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-200 ${
                  isActive
                    ? "bg-amber-400/20 text-amber-400"
                    : "bg-white/5 text-sky-300/60 group-hover:bg-white/10 group-hover:text-sky-200"
                }`}
              >
                <Icon className="w-[18px] h-[18px]" />
              </div>
              <div>
                <span className="block leading-tight">{item.label}</span>
                <span
                  className={`text-[10px] ${
                    isActive ? "text-sky-300/70" : "text-sky-400/40"
                  }`}
                >
                  {item.desc}
                </span>
              </div>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-amber-400" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Section */}
      <div className="p-4 space-y-3">
        <div className="mx-1 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />

        {/* Status Card */}
        <div className="px-4 py-3 bg-white/5 rounded-xl border border-white/10 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <Shield className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-white">All Systems Active</p>
              <p className="text-[10px] text-emerald-400/80">AI Agent Online</p>
            </div>
          </div>
        </div>

        {/* Support Line */}
        <div className="flex items-center gap-2 px-4 py-2 text-sky-400/50">
          <Headphones className="w-3.5 h-3.5" />
          <span className="text-[10px] tracking-wide">24/7 Customer Support</span>
        </div>
      </div>
    </aside>
  );
}
