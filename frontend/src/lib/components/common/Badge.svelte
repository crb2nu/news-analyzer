<script lang="ts">
	import { cn } from '$lib/utils/cn';

	type Variant = 'default' | 'primary' | 'secondary' | 'accent' | 'success' | 'warning' | 'danger';
	type Size = 'sm' | 'md' | 'lg';

	export let variant: Variant = 'default';
	export let size: Size = 'md';

	let className: string = '';
	export { className as class };

	const variantClasses: Record<Variant, string> = {
		default: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200',
		primary: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
		secondary: 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200',
		accent: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
		success: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
		warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
		danger: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
	};

	const sizeClasses: Record<Size, string> = {
		sm: 'px-2 py-0.5 text-xs',
		md: 'px-2.5 py-1 text-sm',
		lg: 'px-3 py-1.5 text-base'
	};

	$: classes = cn(
		'inline-flex items-center font-medium rounded-full',
		variantClasses[variant],
		sizeClasses[size],
		className
	);
</script>

<span class={classes}>
	<slot />
</span>
