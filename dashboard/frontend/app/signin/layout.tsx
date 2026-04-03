import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign In — Buddy",
  description: "Sign in to your Buddy account.",
};

export default function SigninLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
