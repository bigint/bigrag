export type LoginFormValues = {
  email: string;
  password: string;
};

export type SetupFormValues = LoginFormValues & {
  confirm: string;
  displayName: string;
};

export const defaultLoginFormValues = (): LoginFormValues => ({
  email: "",
  password: "",
});

export const defaultSetupFormValues = (): SetupFormValues => ({
  confirm: "",
  displayName: "",
  email: "",
  password: "",
});

export const validateEmail = (email: string): string | undefined => {
  if (!email) return "Email is required";
  if (!/^[^\s@]+@[^\s@]+$/.test(email)) return "Enter a valid email";
  return undefined;
};

export const validatePassword = (password: string): string | undefined => {
  if (!password) return "Password is required";
  if (password.length < 8) return "Password must be at least 8 characters";
  return undefined;
};

export const validateLoginFormValues = ({ email, password }: LoginFormValues): string | undefined =>
  validateEmail(email) ?? validatePassword(password);

export const validateSetupFormValues = ({
  confirm,
  email,
  password,
}: SetupFormValues): string | undefined =>
  validateEmail(email) ??
  validatePassword(password) ??
  (confirm
    ? confirm.length < 8
      ? "Confirm password must be at least 8 characters"
      : password === confirm
        ? undefined
        : "Passwords do not match"
    : "Confirm password is required");

export const loginBodyFromValues = ({ email, password }: LoginFormValues) => ({
  email,
  password,
});

export const setupBodyFromValues = ({ displayName, email, password }: SetupFormValues) => ({
  display_name: displayName,
  email,
  password,
});
