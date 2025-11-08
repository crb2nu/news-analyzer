export function formatDate(isoDate: string): string {
	const date = new Date(isoDate);
	return date.toLocaleDateString('en-US', {
		weekday: 'short',
		month: 'short',
		day: 'numeric'
	});
}

export function formatDateTime(isoDateTime: string | null): string | null {
	if (!isoDateTime) return null;

	const date = new Date(isoDateTime);
	return date.toLocaleString('en-US', {
		month: 'short',
		day: 'numeric',
		hour: 'numeric',
		minute: '2-digit'
	});
}

export function formatDateOption(date: string, total: number, summarized: number): string {
	const formatted = formatDate(date);
	return `${formatted} (${summarized}/${total})`;
}
