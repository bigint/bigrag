import type { FormEvent } from "react";
import { describe, expect, it, vi } from "vitest";
import { errorText, firstString, submitWith } from "./form";

describe("form helpers", () => {
  it("extracts string errors from TanStack error arrays", () => {
    expect(firstString([undefined, "Required", "Other"])).toBe("Required");
    expect(firstString([undefined, null, { message: "Nope" }])).toBeNull();
    expect(errorText(["First", undefined, "Second"])).toBe("First, Second");
    expect(errorText([undefined, null])).toBeNull();
  });

  it("wraps submit handlers with preventDefault and pre-submit work", () => {
    const preventDefault = vi.fn();
    const beforeSubmit = vi.fn();
    const handleSubmit = vi.fn();

    submitWith(handleSubmit, beforeSubmit)({
      preventDefault,
    } as unknown as FormEvent<HTMLFormElement>);

    expect(preventDefault).toHaveBeenCalledOnce();
    expect(beforeSubmit).toHaveBeenCalledOnce();
    expect(handleSubmit).toHaveBeenCalledOnce();
  });
});
