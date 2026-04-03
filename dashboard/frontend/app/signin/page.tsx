"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import AuthLayout from "@/components/auth/AuthLayout";
import GitHubButton from "@/components/auth/GitHubButton";
import TextInput from "@/components/auth/TextInput";

export default function SigninPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });
  const [submitPath, setSubmitPath] = useState<"github" | "email" | null>(null);
  const [credentialsError, setCredentialsError] = useState("");

  const isValidEmail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  const emailError = touched.email && !isValidEmail ? "INVALID EMAIL" : "";
  const passwordError = touched.password && password.length === 0 ? "REQUIRED" : "";

  function handleGitHub() {
    setSubmitPath("github");
    signIn("github", { callbackUrl: "/" });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ email: true, password: true });
    if (!isValidEmail || password.length === 0) return;
    setCredentialsError("");
    setSubmitPath("email");
    const result = await signIn("credentials", { email, password, redirect: false });
    if (result?.error) {
      setCredentialsError("INVALID CREDENTIALS");
      setSubmitPath(null);
      return;
    }
    router.push("/");
  }

  return (
    <AuthLayout>
      <h1 className="text-[clamp(28px,5vw,40px)] font-bold uppercase tracking-[0.05em] mb-16">
        SIGN IN
      </h1>

      <GitHubButton
        onClick={handleGitHub}
        disabled={submitPath !== null}
        label={submitPath === "github" ? "REDIRECTING..." : undefined}
      />

      {credentialsError && (
        <p
          id="credentials-error"
          role="alert"
          className="text-[var(--color-error)] text-xs tracking-[0.1em] mb-6"
        >
          {credentialsError}
        </p>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <TextInput
          id="signin-email"
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
          id="signin-password"
          type="password"
          value={password}
          onChange={setPassword}
          onBlur={() => setTouched((t) => ({ ...t, password: true }))}
          placeholder="PASSWORD"
          autoComplete="current-password"
          disabled={submitPath !== null}
          error={passwordError}
          errorId="password-error"
        />

        <button
          type="submit"
          disabled={submitPath !== null}
          className="w-full border-2 border-[var(--color-border-hover)] bg-transparent text-[var(--color-text)] font-bold text-sm uppercase tracking-[0.1em] py-4 px-6 cursor-pointer hover:bg-[var(--color-text)] hover:text-[var(--color-bg)] disabled:opacity-50 disabled:cursor-not-allowed mt-4"
        >
          {submitPath === "email" ? "SIGNING IN..." : "SIGN IN"}
        </button>
      </form>

      <p className="text-[var(--color-text-dim)] text-xs tracking-[0.05em] mt-12 text-center">
        Don&apos;t have an account?{" "}
        <a href="/signup" className="text-[var(--color-text-dim)] underline hover:text-[var(--color-success)]">
          Sign up
        </a>
      </p>
    </AuthLayout>
  );
}
