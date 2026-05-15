import { describe, expect, it } from "vitest";
import {
  defaultPasswordFormValues,
  defaultProfileFormValues,
  passwordBodyFromValues,
  profileBodyFromValues,
  profileFormHasChanges,
  profileFormValuesFromUser,
  validatePasswordFormValues,
  validateProfileEmail,
  validateProfileFormValues,
} from "./account-form-state";

describe("account form state", () => {
  it("builds and validates profile form values", () => {
    expect(defaultProfileFormValues()).toEqual({
      displayName: "",
      email: "",
    });
    expect(
      profileFormValuesFromUser({
        created_at: "2026-01-01T00:00:00Z",
        display_name: "Admin",
        email: "admin@example.com",
        id: "user-1",
        last_login_at: null,
        role: "admin",
        updated_at: "2026-01-01T00:00:00Z",
      }),
    ).toEqual({
      displayName: "Admin",
      email: "admin@example.com",
    });
    expect(validateProfileFormValues({ displayName: "", email: "" })).toBe("Email is required");
    expect(validateProfileEmail("admin")).toBe("Enter a valid email");
    expect(validateProfileFormValues({ displayName: "", email: "admin" })).toBe(
      "Enter a valid email",
    );
    expect(
      validateProfileFormValues({
        displayName: "x".repeat(121),
        email: "admin@example.com",
      }),
    ).toBe("Display name must be 120 characters or fewer");
  });

  it("preserves profile payload shape and change detection", () => {
    expect(profileBodyFromValues({ displayName: " Admin ", email: " Admin@Example.com " })).toEqual(
      {
        display_name: "Admin",
        email: "Admin@Example.com",
      },
    );
    expect(
      profileFormHasChanges(
        { displayName: "Admin", email: "admin@example.com" },
        { displayName: " Admin ", email: "ADMIN@example.com" },
      ),
    ).toBe(false);
    expect(
      profileFormHasChanges(
        { displayName: "Admin", email: "admin@example.com" },
        { displayName: "Yoginth", email: "admin@example.com" },
      ),
    ).toBe(true);
  });

  it("builds default password form values", () => {
    expect(defaultPasswordFormValues()).toEqual({
      confirm: "",
      current: "",
      next: "",
    });
  });

  it("validates password change submissions", () => {
    expect(validatePasswordFormValues(defaultPasswordFormValues())).toBe(
      "Current password is required",
    );
    expect(
      validatePasswordFormValues({
        confirm: "",
        current: "current-password",
        next: "",
      }),
    ).toBe("New password is required");
    expect(
      validatePasswordFormValues({
        confirm: "new-password",
        current: "current-password",
        next: "different-password",
      }),
    ).toBe("Passwords do not match");
  });

  it("preserves the password payload shape", () => {
    expect(
      passwordBodyFromValues({
        confirm: "new-password",
        current: "current-password",
        next: "new-password",
      }),
    ).toEqual({
      current_password: "current-password",
      new_password: "new-password",
    });
  });
});
