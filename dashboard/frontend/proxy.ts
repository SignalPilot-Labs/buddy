import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const isAuthenticated = !!req.auth;
  const path = req.nextUrl.pathname;

  // Auth pages are public
  const publicPaths = ["/signin", "/signup", "/api/auth"];
  const isPublic = publicPaths.some((p) => path.startsWith(p));

  if (isPublic) return NextResponse.next();

  // Everything else requires authentication
  if (!isAuthenticated) {
    const signinUrl = new URL("/signin", req.nextUrl.origin);
    return NextResponse.redirect(signinUrl);
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon|.*\\..*).*)"],
};
