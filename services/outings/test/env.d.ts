declare namespace Cloudflare {
	interface Env {
		DB: D1Database;
		APP_ORIGIN: string;
		RP_ID: string;
		RP_NAME: string;
		APP_URL: string;
		VAPID_PRIVATE_JWK?: string;
		VAPID_SUBJECT?: string;
		TEST_MIGRATIONS: { name: string; queries: string[] }[];
	}
	// tipi di `exports` (cloudflare:workers) nei test: il modulo principale del Worker
	interface GlobalProps {
		mainModule: typeof import('../src/index');
	}
}
