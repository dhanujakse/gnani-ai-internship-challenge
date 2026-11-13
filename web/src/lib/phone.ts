// Port of the app's normalizePhoneE164 + sha256Hex (ui/screens/ContactsScreens.kt), so a number entered on the web
// hashes to exactly the same value as on a phone and contact discovery matches.

export function normalizePhoneE164(raw: string, defaultCountryCode = "+91"): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  let cleaned = trimmed.replace(/[^0-9+]/g, "");
  if (cleaned.startsWith("+")) {
    const digits = cleaned.slice(1).replace(/\D/g, "");
    return digits.length >= 7 && digits.length <= 15 ? `+${digits}` : null;
  }
  if (cleaned.startsWith("00")) {
    const digits = cleaned.slice(2).replace(/\D/g, "");
    return digits.length >= 7 && digits.length <= 15 ? `+${digits}` : null;
  }
  cleaned = cleaned.replace(/\+/g, "");
  if (cleaned.startsWith("0") && cleaned.length === 11) return `${defaultCountryCode}${cleaned.slice(1)}`;
  if (cleaned.length === 10) return `${defaultCountryCode}${cleaned}`;
  if (cleaned.length === 12 && cleaned.startsWith("91")) return `+${cleaned}`;
  if (cleaned.length >= 7 && cleaned.length <= 15) return `${defaultCountryCode}${cleaned}`;
  return null;
}

export async function sha256Hex(s: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function phoneHash(raw: string): Promise<string | null> {
  const e164 = normalizePhoneE164(raw);
  return e164 ? sha256Hex(e164) : null;
}
