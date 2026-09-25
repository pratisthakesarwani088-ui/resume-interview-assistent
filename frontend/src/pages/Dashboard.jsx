import { useState } from "react";
import Navbar from "../components/Navbar.jsx";
import { useAuth } from "../context/AuthContext.jsx";

export default function Dashboard() {
  const { user, updateProfile } = useAuth();
  const [form, setForm] = useState({ name: user?.name ?? "", email: user?.email ?? "" });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState("idle"); // idle | saving | saved

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});
    setStatus("saving");
    try {
      await updateProfile(form);
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
        <h1 className="text-lg font-semibold text-slate-50">Your profile</h1>
        <p className="mt-1 text-sm text-slate-400">
          Name and email are the only details stored here.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 max-w-sm space-y-4">
          <div>
            <label htmlFor="name" className="mb-1.5 block text-sm text-slate-300">
              Name
            </label>
            <input
              id="name"
              name="name"
              value={form.name}
              onChange={handleChange}
              required
              className={`w-full rounded-md border bg-surface-raised px-3 py-2.5 text-sm text-slate-100 outline-none transition-colors focus:border-accent ${
                errors.name ? "border-red-500/50" : "border-surface-border"
              }`}
            />
            {errors.name && <p className="mt-1.5 text-xs text-red-400">{errors.name}</p>}
          </div>

          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm text-slate-300">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              required
              className={`w-full rounded-md border bg-surface-raised px-3 py-2.5 text-sm text-slate-100 outline-none transition-colors focus:border-accent ${
                errors.email ? "border-red-500/50" : "border-surface-border"
              }`}
            />
            {errors.email && <p className="mt-1.5 text-xs text-red-400">{errors.email}</p>}
          </div>

          <button
            type="submit"
            disabled={status === "saving"}
            className="rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {status === "saving" ? "Saving…" : status === "saved" ? "Saved" : "Save changes"}
          </button>
        </form>
      </main>
    </div>
  );
}
