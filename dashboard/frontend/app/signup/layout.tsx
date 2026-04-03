import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign Up — Buddy",
  description: "Create your Buddy account.",
};

export default function SignupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
