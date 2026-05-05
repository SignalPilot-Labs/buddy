import "@testing-library/jest-dom/vitest";

// Mock the API key that constants.ts reads at module load time
(window as unknown as Record<string, string>).__AUTOFYN_API_KEY__ = "test-key";
