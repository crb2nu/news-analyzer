import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export type Theme = 'light' | 'dark' | 'system';

function createThemeStore() {
	const { subscribe, set } = writable<Theme>('system');

	// Initialize from localStorage
	if (browser) {
		const stored = localStorage.getItem('theme') as Theme | null;
		if (stored && ['light', 'dark', 'system'].includes(stored)) {
			set(stored);
		}
	}

	return {
		subscribe,
		set: (value: Theme) => {
			if (browser) {
				localStorage.setItem('theme', value);
				applyTheme(value);
			}
			set(value);
		}
	};
}

function applyTheme(mode: Theme) {
	if (!browser) return;

	const root = document.documentElement;

	if (mode === 'dark') {
		root.setAttribute('data-theme', 'dark');
		root.classList.add('dark');
	} else if (mode === 'light') {
		root.setAttribute('data-theme', 'light');
		root.classList.remove('dark');
	} else {
		// System preference
		const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
		root.setAttribute('data-theme', isDark ? 'dark' : 'light');
		root.classList.toggle('dark', isDark);
	}
}

export const theme = createThemeStore();

// Apply theme on initialization
if (browser) {
	const stored = (localStorage.getItem('theme') as Theme) || 'system';
	applyTheme(stored);

	// Listen for system theme changes
	window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
		const currentTheme = localStorage.getItem('theme') as Theme;
		if (currentTheme === 'system') {
			applyTheme('system');
		}
	});
}
