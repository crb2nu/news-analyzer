import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const READ_KEY = 'news-analyzer-read-v1';

function createReadArticlesStore() {
	const initialValue = browser
		? new Set<number>(JSON.parse(localStorage.getItem(READ_KEY) || '[]'))
		: new Set<number>();

	const { subscribe, set, update } = writable<Set<number>>(initialValue);

	return {
		subscribe,
		add: (id: number) => {
			update((set) => {
				set.add(id);
				if (browser) {
					localStorage.setItem(READ_KEY, JSON.stringify([...set]));
				}
				return new Set(set);
			});
		},
		remove: (id: number) => {
			update((set) => {
				set.delete(id);
				if (browser) {
					localStorage.setItem(READ_KEY, JSON.stringify([...set]));
				}
				return new Set(set);
			});
		},
		toggle: (id: number) => {
			update((set) => {
				if (set.has(id)) {
					set.delete(id);
				} else {
					set.add(id);
				}
				if (browser) {
					localStorage.setItem(READ_KEY, JSON.stringify([...set]));
				}
				return new Set(set);
			});
		},
		clear: () => {
			set(new Set());
			if (browser) {
				localStorage.setItem(READ_KEY, JSON.stringify([]));
			}
		}
	};
}

export const readArticles = createReadArticlesStore();
