import { useState } from "react";
import Navbar from "../components/Navbar.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const initialForm = { old_password: "", new_password: "", confirm_new_password: "" };

export default function ChangePassword() {
  const { changePassword } = useAuth();
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState("idle"); // idle | saving | saved

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});
    setStatus("saving");
    try {
      await changePassword(form);
      setForm(initialForm);
      setStatus("saved");
      setTimeout(() => setStatus("idle"), 2000);
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === "object") {
        const flat = {};
        Object.entries(data).forEach(([key, value]) => {
          flat[key] = Array.isArray(value) ? value.join(" ") : String(value);
        });
        setErrors(flat);
      }
      setStatus("idle");
    }
  };

  return (
    <div className="min-h-screen bg-surface">
      <Navbar />
      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-lg font-semibold text-slate-50">Change password</h1>
        <p className="mt-1 text-sm text-slate-400">
          Use a password you're not using anywhere else.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 max-w-sm space-y-4">
          {errors.non_field_errors && (
            <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
              {errors.non_field_errors}
            </p>
          )}

          <PasswordField
            label="Current password"
            name="old_password"
            value={form.old_password}
            onChange={handleChange}
            error={errors.old_password}
          />
          <PasswordField
            label="New password"
            name="new_password"
            value={form.new_password}
            onChange={handleChange}
            error={errors.new_password}
          />
          <PasswordField
            label="Confirm new password"
            name="confirm_new_password"
            value={form.confirm_new_password}
            onChange={handleChange}
            error={errors.confirm_new_password}
          />

          <button
            type="submit"
            disabled={status === "saving"}
            className="rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {status === "saving" ? "Updating…" : status === "saved" ? "Updated" : "Update password"}
          </button>
        </form>
      </main>
    </div>
  );
}

function PasswordField({ label, name, value, onChange, error }) {
  return (
    <div>
      <label htmlFor={name} className="mb-1.5 block text-sm text-slate-300">
        {label}
      </label>
      <input
        id={name}
        name={name}
        type="password"
        value={value}
        onChange={onChange}
        autoComplete="new-password"
        required
        className={`w-full rounded-md border bg-surface-raised px-3 py-2.5 text-sm text-slate-100 outline-none transition-colors focus:border-accent ${
          error ? "border-red-500/50" : "border-surface-border"
        }`}
      />
      {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
    </div>
  );
}
