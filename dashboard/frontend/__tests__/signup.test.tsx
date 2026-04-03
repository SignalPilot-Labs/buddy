import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import SignupPage from "@/app/signup/page";

const pushMock = vi.fn();
const signInMock = vi.fn().mockResolvedValue({ error: null });

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("next-auth/react", () => ({
  signIn: (...args: unknown[]) => signInMock(...args),
  signOut: vi.fn(),
  useSession: () => ({ data: null, status: "unauthenticated" }),
}));

const fetchMock = vi.fn();
global.fetch = fetchMock as unknown as typeof fetch;

beforeEach(() => {
  pushMock.mockClear();
  signInMock.mockClear();
  signInMock.mockResolvedValue({ error: null });
  fetchMock.mockClear();
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => ({}),
  });
});

describe("SignupPage", () => {
  it("renders GitHub OAuth button", () => {
    render(<SignupPage />);
    expect(screen.getByRole("button", { name: /continue with github/i })).toBeInTheDocument();
  });

  it("GitHub button calls signIn with correct args", () => {
    render(<SignupPage />);
    fireEvent.click(screen.getByRole("button", { name: /continue with github/i }));
    expect(signInMock).toHaveBeenCalledWith("github", { callbackUrl: "/" });
  });

  it("shows email error on blur with invalid email", () => {
    render(<SignupPage />);
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: "notanemail" } });
    fireEvent.blur(emailInput);
    expect(screen.getByText("INVALID EMAIL")).toBeInTheDocument();
  });

  it("shows no email error for valid email", () => {
    render(<SignupPage />);
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.blur(emailInput);
    expect(screen.queryByText("INVALID EMAIL")).not.toBeInTheDocument();
  });

  it("shows password error on blur when too short", () => {
    render(<SignupPage />);
    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: "short" } });
    fireEvent.blur(passwordInput);
    expect(screen.getByText("MIN 8 CHARACTERS")).toBeInTheDocument();
  });

  it("shows no password error for valid password", () => {
    render(<SignupPage />);
    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: "longpassword" } });
    fireEvent.blur(passwordInput);
    expect(screen.queryByText("MIN 8 CHARACTERS")).not.toBeInTheDocument();
  });

  it("blocks submission with invalid inputs and shows errors", () => {
    render(<SignupPage />);
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(screen.getByText("INVALID EMAIL")).toBeInTheDocument();
    expect(screen.getByText("MIN 8 CHARACTERS")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("email submission calls fetch then signIn then router.push", async () => {
    render(<SignupPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "test@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "longpassword" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/signup", expect.objectContaining({ method: "POST" }));
    expect(signInMock).toHaveBeenCalledWith("credentials", expect.objectContaining({ email: "test@example.com", password: "longpassword", redirect: false }));
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("shows CREATING... during email submission", async () => {
    let resolveFetch!: () => void;
    fetchMock.mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = () =>
          resolve({ ok: true, json: async () => ({}) } as Response);
      })
    );
    render(<SignupPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "test@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "longpassword" } });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });
    expect(screen.getByRole("button", { name: /creating/i })).toBeInTheDocument();
    await act(async () => { resolveFetch(); });
  });

  it("shows REDIRECTING... during GitHub submission", () => {
    render(<SignupPage />);
    fireEvent.click(screen.getByRole("button", { name: /continue with github/i }));
    expect(screen.getByRole("button", { name: /redirecting/i })).toBeInTheDocument();
  });

  it("disables buttons during GitHub submission", () => {
    render(<SignupPage />);
    fireEvent.click(screen.getByRole("button", { name: /continue with github/i }));
    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
  });

  it("shows API error when fetch returns error response", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ error: "EMAIL_EXISTS" }),
    });
    render(<SignupPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "test@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "longpassword" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });
    expect(screen.getByText("EMAIL_EXISTS")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("sign in link points to /signin", () => {
    render(<SignupPage />);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/signin");
  });

  it("renders main landmark", () => {
    render(<SignupPage />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("email input has autocomplete='email'", () => {
    render(<SignupPage />);
    expect(screen.getByLabelText(/email/i)).toHaveAttribute("autocomplete", "email");
  });

  it("password input has autocomplete='new-password'", () => {
    render(<SignupPage />);
    expect(screen.getByLabelText(/password/i)).toHaveAttribute("autocomplete", "new-password");
  });
});
