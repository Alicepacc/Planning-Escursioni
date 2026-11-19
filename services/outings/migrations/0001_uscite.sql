-- Uscite di gruppo (SPEC §5.4, ADR 0014). Solo i dati che servono: niente email, niente
-- telefoni; il nome mostrato lo sceglie la persona.

CREATE TABLE utenti (
	id TEXT PRIMARY KEY,
	nome TEXT NOT NULL,
	creato TEXT NOT NULL DEFAULT (datetime('now'))
);

-- credenziali WebAuthn (passkey): una persona può averne più d'una (telefono, computer)
CREATE TABLE passkey (
	id TEXT PRIMARY KEY,
	utente TEXT NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
	chiave_pubblica BLOB NOT NULL,
	contatore INTEGER NOT NULL DEFAULT 0,
	trasporti TEXT,
	creato TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX passkey_utente ON passkey(utente);

-- sfide WebAuthn monouso, valide pochi minuti
CREATE TABLE sfide (
	id TEXT PRIMARY KEY,
	sfida TEXT NOT NULL,
	utente TEXT,
	tipo TEXT NOT NULL CHECK (tipo IN ('registrazione', 'accesso')),
	scade TEXT NOT NULL
);

-- sessioni: si conserva solo l'hash del token
CREATE TABLE sessioni (
	hash TEXT PRIMARY KEY,
	utente TEXT NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
	scade TEXT NOT NULL
);
CREATE INDEX sessioni_utente ON sessioni(utente);

CREATE TABLE uscite (
	id TEXT PRIMARY KEY,
	-- hash del segreto del link d'invito: senza il link la pagina non si legge
	invito_hash TEXT NOT NULL,
	organizzatore TEXT NOT NULL REFERENCES utenti(id),
	titolo TEXT NOT NULL,
	-- riferimento all'itinerario dell'app (scheda di attività, itinerario o piano)
	itinerario TEXT,
	ritrovo_quando TEXT NOT NULL,
	ritrovo_luogo TEXT NOT NULL,
	ritrovo_lon REAL,
	ritrovo_lat REAL,
	mezzi TEXT,
	posti INTEGER CHECK (posti IS NULL OR posti > 0),
	iscrizioni_entro TEXT,
	difficolta TEXT,
	requisiti TEXT,
	attrezzatura TEXT NOT NULL DEFAULT '[]',
	note TEXT,
	visibilita TEXT NOT NULL DEFAULT 'link' CHECK (visibilita IN ('link', 'contatti', 'pubblica')),
	stato TEXT NOT NULL DEFAULT 'aperta' CHECK (stato IN ('aperta', 'annullata', 'rinviata')),
	rinviata_a TEXT,
	creato TEXT NOT NULL DEFAULT (datetime('now')),
	aggiornato TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX uscite_organizzatore ON uscite(organizzatore);
CREATE INDEX uscite_pubbliche ON uscite(visibilita, ritrovo_quando);

CREATE TABLE partecipanti (
	uscita TEXT NOT NULL REFERENCES uscite(id) ON DELETE CASCADE,
	utente TEXT NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
	stato TEXT NOT NULL CHECK (stato IN ('confermato', 'attesa', 'rinunciato')),
	iscritto TEXT NOT NULL DEFAULT (datetime('now')),
	aggiornato TEXT NOT NULL DEFAULT (datetime('now')),
	PRIMARY KEY (uscita, utente)
);

-- bacheca: solo l'organizzatore scrive, i partecipanti leggono
CREATE TABLE annunci (
	id TEXT PRIMARY KEY,
	uscita TEXT NOT NULL REFERENCES uscite(id) ON DELETE CASCADE,
	testo TEXT NOT NULL,
	creato TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX annunci_uscita ON annunci(uscita, creato);

-- iscrizioni alle notifiche Web Push del browser
CREATE TABLE notifiche_push (
	endpoint TEXT PRIMARY KEY,
	utente TEXT NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
	p256dh TEXT NOT NULL,
	auth TEXT NOT NULL,
	creato TEXT NOT NULL DEFAULT (datetime('now'))
);
