import { goto } from '$app/navigation';

export function updateUrlParams(params: Record<string, string | undefined>) {
	const url = new URL(window.location.href);

	Object.entries(params).forEach(([key, value]) => {
		if (value && value !== '') {
			url.searchParams.set(key, value);
		} else {
			url.searchParams.delete(key);
		}
	});

	const newUrl = url.searchParams.toString() ? `?${url.searchParams.toString()}` : url.pathname;
	goto(newUrl, { replaceState: true, noScroll: true, keepFocus: true });
}
