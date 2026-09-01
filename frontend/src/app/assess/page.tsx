"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Legacy /assess route — no session_id means no valid assessment.
// Redirect to the landing page so users can pick scope first.
export default function AssessLegacy() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark">
      <div className="text-silver-muted">Redirecting...</div>
    </div>
  );
}
