import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoBrain: honest EV advice",
  description: "Honest, evidence-backed EV buying advice for Mahindra and Tata buyers in India.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-surface font-sans text-ink antialiased">{children}</body>
    </html>
  );
}
