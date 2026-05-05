import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "./sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Shaheen Airline - Customer Support Portal",
  description:
    "Shaheen Airline AI-powered customer support platform - Book flights, manage reservations, and get instant help",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-screen flex bg-background text-foreground">
        <Sidebar />
        <main className="flex-1 ml-72 min-h-screen">
          <div className="p-8 lg:p-10">{children}</div>
        </main>
      </body>
    </html>
  );
}
