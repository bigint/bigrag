import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";
import { errorToast } from "./mutation-toast";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
  },
}));

describe("errorToast", () => {
  it("uses error messages and falls back for non-errors", () => {
    errorToast("Fallback")(new Error("Specific"));
    errorToast("Fallback")("nope");

    expect(toast.error).toHaveBeenNthCalledWith(1, "Specific");
    expect(toast.error).toHaveBeenNthCalledWith(2, "Fallback");
  });
});
