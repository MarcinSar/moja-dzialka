import { useState } from 'react';
import { Loader2, Send, CheckCircle } from 'lucide-react';

export function LeadCaptureSection({ parcelId }: { parcelId: string }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const response = await fetch('/api/v1/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parcel_id: parcelId, name, email, phone: phone || null }),
      });
      if (!response.ok) throw new Error('Nie udało się wysłać zgłoszenia');
      setIsSubmitted(true);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Wystąpił błąd');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-center">
        <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
        <p className="text-sm text-white font-medium">Dziękujemy!</p>
        <p className="text-xs text-slate-400 mt-1">Skontaktujemy się wkrótce.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Zainteresowany?</h3>
      <form onSubmit={handleSubmit} className="space-y-2">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10
                     text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-sky-500/50"
          placeholder="Imię"
        />
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10
                     text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-sky-500/50"
          placeholder="Email"
        />
        <input
          type="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10
                     text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-sky-500/50"
          placeholder="Telefon (opcjonalnie)"
        />
        {submitError && <p className="text-red-400 text-xs">{submitError}</p>}
        <button
          type="submit"
          disabled={isSubmitting || !name || !email}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg
                     bg-amber-500 text-slate-900 text-xs font-medium
                     hover:bg-amber-400 transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
          <span>{isSubmitting ? 'Wysyłanie...' : 'Wyślij zgłoszenie'}</span>
        </button>
      </form>
    </div>
  );
}
