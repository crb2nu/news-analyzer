import { PUBLIC_API_BASE_URL } from '$env/static/public';

export class APIError extends Error {
	constructor(
		public status: number,
		public statusText: string,
		public detail?: string
	) {
		super(`API Error ${status}: ${statusText}`);
		this.name = 'APIError';
	}
}

export async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
	const url = `${PUBLIC_API_BASE_URL}${endpoint}`;

	try {
		const response = await fetch(url, {
			...options,
			headers: {
				'Content-Type': 'application/json',
				...options?.headers
			}
		});

		if (!response.ok) {
			const detail = await response.text().catch(() => '');
			throw new APIError(response.status, response.statusText, detail);
		}

		return response.json();
	} catch (error) {
		if (error instanceof APIError) throw error;
		throw new APIError(0, 'Network Error', String(error));
	}
}
