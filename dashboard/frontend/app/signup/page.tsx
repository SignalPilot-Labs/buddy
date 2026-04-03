"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import AuthLayout from "@/components/auth/AuthLayout";
import GitHubButton from "@/components/auth/GitHubButton";
import TextInput from "@/components/auth/TextInput";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });
  const [submitPath, setSubmitPath] = useState<"github" | "email" | null>(null);
  const [apiError, setApiError] = useState<string>("");

  const isValidEmail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  const emailError = touched.email && !isValidEmail ? "INVALID EMAIL" : "";
  const passwordError = touched.password && password.length < 8 ? "MIN 8 CHARACTERS" : "";

  function handleGitHub() {
    setSubmitPath("github");
    signIn("github", { callbackUrl: "/" });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ email: true, password: true });
    if (!isValidEmail || password.length < 8) return;
    setSubmitPath("email");
    setApiError("");

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setApiError(data.error ?? "SIGNUP_FAILED");
        setSubmitPath(null);
        return;
      }

      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        setApiError(result.error);
        setSubmitPath(null);
        return;
      }

      router.push("/");
    } catch {
      setApiError("NETWORK_ERROR");
      setSubmitPath(null);
    }
  }

  return (
    <AuthLayout>
      <h1 className="text-[clamp(28px,5vw,40px)] font-bold uppercase tracking-[0.05em] mb-16">
        CREATE ACCOUNT
      </h1>

      <GitHubButton
        onClick={handleGitHub}
        disabled={submitPath !== null}
        label={submitPath === "github" ? "REDIRECTING..." : undefined}
      />

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <TextInput
          id="signup-email"
          type="email"
          value={email}
          onChange={setEmail}
          onBlur={() => setTouched((t) => ({ ...t, email: true }))}
          placeholder="EMAIL"
          autoComplete="email"
          disabled={submitPath !== null}
          error={emailError}
          errorId="email-error"
        />

        <TextInput
          id="signup-password"
          type="password"
          value={password}
          onChange={setPassword}
          onBlur={() => setTouched((t) => ({ ...t, password: true }))}
          placeholder="PASSWORD"
          autoComplete="new-password"
          disabled={submitPath !== null}
          error={passwordError}
          errorId="password-error"
        />

        {apiError && (
          <p id="api-error" role="alert" className="text-[var(--color-error)] text-xs tracking-[0.1em]">{apiError}</p>
        )}

        <button
          type="submit"
          disabled={submitPath !== null}
          className="w-full border-2 border-[var(--color-border-hover)] bg-transparent text-[var(--color-text)] font-bold text-sm uppercase tracking-[0.1em] py-4 px-6 cursor-pointer hover:bg-[var(--color-text)] hover:text-[var(--color-bg)] disabled:opacity-50 disabled:cursor-not-allowed mt-4"
        >
          {submitPath === "email" ? "CREATING..." : "CREATE ACCOUNT"}
        </button>
      </form>

      <p className="text-[var(--color-text-dim)] text-xs tracking-[0.05em] mt-12 text-center">
        Already have an account?{" "}
        <a href="/signin" className="text-[var(--color-text-dim)] underline hover:text-[var(--color-success)]">
          Sign in
        </a>
      </p>
    </AuthLayout>
  );
}
