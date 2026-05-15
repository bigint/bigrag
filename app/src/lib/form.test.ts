import { describe, expect, it, vi } from "vitest";
import { errorText, firstString, submitWith } from "./form";

describe("form helpers", () => {
  it("extracts string errors", () => {
    expect(firstString([undefined, "Required", "Other"])).toBe("Required");
    expect(errorText(["Required", undefined, "Other"])).toBe("Required, Other");
    expect(errorText([undefined])).toBeNull();
  });

  it("wraps form submit handlers", () => {
    const handleSubmit = vi.fn();
    const beforeSubmit = vi.fn();
    const preventDefault = vi.fn();

    submitWith(
      handleSubmit,
      beforeSubmit,
    )({
      preventDefault,
    } as unknown as React.FormEvent<HTMLFormElement>);

    expect(preventDefault).toHaveBeenCalled();
    expect(beforeSubmit).toHaveBeenCalled();
    expect(handleSubmit).toHaveBeenCalled();
  });
});
