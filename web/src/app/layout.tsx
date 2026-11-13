import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sarvagyan — Speak Naturally. Understand Everyone.",
  description:
    "Real-time multilingual voice translation and calling powered by Gnani AI. Live speech recognition, instant translation across 10 Indian languages, and neural voice playback.",
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col bg-[#071B20] text-[#F5F7F2] antialiased">
        {children}
      </body>
    </html>
  );
}
