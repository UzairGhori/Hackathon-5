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
    <aside className="fixed left-0 top-0 h-screen w-72 bg-shaheen-navy flex flex-col z-50 shadow-2xl">
      {/* Brand Header */}
      <div className="p-8 pb-6">
        <div className="flex flex-col gap-4">
          <div className="w-16 h-16 rounded-2xl bg-white flex items-center justify-center shadow-xl border-2 border-shaheen-green">
            <Plane className="w-10 h-10 text-shaheen-navy" />
          </div>
          <div>
            <h1 className="font-extrabold text-xl text-white tracking-tight">
              SHAHEEN
            </h1>
            <p className="text-xs text-shaheen-green font-bold tracking-[0.2em] uppercase -mt-1">
              AIRLINES
            </p>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-8 h-px bg-white/10" />

      {/* Navigation */}
      <nav className="flex-1 px-4 py-8 space-y-2">
        <p className="px-4 mb-4 text-[10px] font-bold text-white/40 uppercase tracking-[0.2em]">
          Marketplace
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
              className={`group flex items-center gap-4 px-4 py-3.5 rounded-xl text-sm font-semibold transition-all duration-300 ${
                isActive
                  ? "bg-white text-shaheen-navy shadow-lg"
                  : "text-white/70 hover:text-white hover:bg-white/5"
              }`}
            >
              <div
                className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-300 ${
                  isActive
                    ? "bg-shaheen-navy/10 text-shaheen-navy"
                    : "bg-white/5 text-white/40 group-hover:bg-white/10 group-hover:text-white"
                }`}
              >
                <Icon className="w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <span className="leading-tight">{item.label}</span>
                <span
                  className={`text-[10px] font-medium ${
                    isActive ? "text-shaheen-navy/60" : "text-white/30"
                  }`}
                >
                  {item.desc}
                </span>
              </div>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-shaheen-green" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Section */}
      <div className="p-6 bg-black/20">
        {/* Status Card */}
        <div className="px-4 py-4 bg-white/5 rounded-2xl border border-white/10 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-shaheen-green/20 flex items-center justify-center">
              <Shield className="w-5 h-5 text-shaheen-green" />
            </div>
            <div>
              <p className="text-xs font-bold text-white">Official Portal</p>
              <p className="text-[10px] text-shaheen-green font-semibold">Verified Secure</p>
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
