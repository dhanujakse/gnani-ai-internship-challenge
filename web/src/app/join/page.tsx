"use client";

// Invitation links (https://…/join?code=ABC234) open the app with the code ready to join after signing in.
import { useEffect } from "react";
import { Logo } from "@/components/ui";

export default function JoinPage() {
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("code") ?? "";
    window.location.replace(code ? `/?code=${encodeURIComponent(code)}` : "/");
  }, []);
  return (
    <div className="grid min-h-dvh place-items-center">
      <Logo size={64} />
    </div>
  );
}
