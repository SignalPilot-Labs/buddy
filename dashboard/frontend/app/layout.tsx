import type { Metadata, Viewport } from "next";
import "./globals.css";
import { MotionProvider } from "@/components/MotionProvider";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#050505",
};

// Disable static page caching so the inline script reads AUTOFYN_API_KEY
// from the server environment on every request (the key isn't available at
// build time).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AutoFyn",
  description: "Real-time monitoring dashboard for the AutoFyn agent",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "AutoFyn",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          rel="preconnect"
          href="https://fonts.googleapis.com"
        />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@100..800&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__AUTOFYN_API_KEY__=${JSON.stringify(process.env.AUTOFYN_API_KEY ?? "").replace(/</g, "\\u003c")};`,
          }}
        />
      </head>
      <body><MotionProvider>{children}</MotionProvider></body>
    </html>
  );
}
