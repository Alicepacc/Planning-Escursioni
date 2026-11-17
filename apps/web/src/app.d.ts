// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		interface PageState {
			/** numero di modifiche del planner dall'apertura (annulla/ripeti con la cronologia) */
			depth?: number;
		}
		// interface Platform {}
	}
}

export {};
