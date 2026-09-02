"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { tokenManager } from "@/lib/auth";
import AuthForm from "@/components/AuthForm";

export default function RegisterPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to dashboard if already authenticated
    if (tokenManager.isAuthenticated()) {
      router.push("/dashboard");
    }
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <AuthForm type="register" />
    </div>
  );
}
