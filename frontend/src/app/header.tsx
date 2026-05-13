"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Plane,
  Shield,
  LayoutDashboard,
  Ticket,
  MessageSquare,
  ChevronDown,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Home", icon: LayoutDashboard },
  { href: "/tickets", label: "Missions", icon: Ticket },
  { href: "/chat", label: "Support", icon: MessageSquare },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 h-20 bg-[#002d5a] z-[100] border-b border-white/10 shadow-2xl px-8 flex items-center justify-between">
      {/* Brand Section */}
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-4 group">
          <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center shadow-lg border-2 border-shaheen-emerald group-hover:scale-105 transition-transform">
            <Plane className="w-7 h-7 text-[#002d5a]" />
          </div>
          <div className="flex flex-col">
            <span className="text-xl font-black text-white tracking-tighter leading-none">SHAHEEN</span>
            <span className="text-[9px] text-shaheen-emerald font-black tracking-[0.3em] uppercase mt-1">AIRLINES</span>
          </div>
        </Link>
        
        {/* Navigation Divider */}
        <div className="h-8 w-px bg-white/10 mx-2 hidden md:block" />
        
        {/* Main Nav */}
        <nav className="hidden md:flex items-center gap-2">
          {navItems.map((item) => {
            const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-5 py-2 rounded-xl text-[11px] font-black uppercase tracking-widest transition-all ${
                  isActive 
                    ? "bg-white text-[#002d5a] shadow-lg" 
                    : "text-white/60 hover:text-white hover:bg-white/5"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-6">
        {/* Services Dropdown - Marketplace Style */}
        <button className="hidden lg:flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-white/80 hover:bg-white/10 transition-all cursor-pointer">
           <span className="text-[10px] font-black uppercase tracking-widest">Global Services</span>
           <ChevronDown className="w-3 h-3 text-shaheen-emerald" />
        </button>

        {/* System Status */}
        <div className="flex items-center gap-4 bg-black/30 px-5 py-2.5 rounded-2xl border border-white/5">
          <div className="flex flex-col items-end">
             <p className="text-[10px] font-black text-white uppercase tracking-wider">Secure Portal</p>
             <p className="text-[8px] text-shaheen-emerald font-black uppercase tracking-widest">Operational</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-shaheen-emerald/10 flex items-center justify-center border border-shaheen-emerald/20">
            <Shield className="w-5 h-5 text-shaheen-emerald" />
          </div>
        </div>
      </div>
    </header>
  );
}
