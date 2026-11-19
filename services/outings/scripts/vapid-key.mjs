// Genera una nuova chiave privata VAPID (P-256, formato JWK) e la scrive su stdout, senza salvarla.
// Da usare solo in pipe verso i segreti di Cloudflare, così non finisce in nessun file:
//   node scripts/vapid-key.mjs | pnpm exec wrangler secret put VAPID_PRIVATE_JWK
const key = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign']);
const { kty, crv, x, y, d } = await crypto.subtle.exportKey('jwk', key.privateKey);
process.stdout.write(JSON.stringify({ kty, crv, x, y, d }));
