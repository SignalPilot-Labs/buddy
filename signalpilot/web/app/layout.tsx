import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/sidebar";

export const metadata: Metadata = {
  title: "SignalPilot",
  description: "Governed sandbox console for AI database access",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <Sidebar />
        <main className="ml-60 min-h-screen">{children}</main>
      </body>
    </html>
  );
}
