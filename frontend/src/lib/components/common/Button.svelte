<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import type { HTMLButtonAttributes, HTMLAnchorAttributes } from 'svelte/elements';

	type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
	type Size = 'sm' | 'md' | 'lg';

	interface BaseProps {
		variant?: Variant;
		size?: Size;
		class?: string;
	}

	type ButtonProps = BaseProps & HTMLButtonAttributes;
	type AnchorProps = BaseProps & HTMLAnchorAttributes & { href: string };
	type $$Props = ButtonProps | AnchorProps;

	export let variant: Variant = 'primary';
	export let size: Size = 'md';

	let className: string = '';
	export { className as class };

	const variantClasses: Record<Variant, string> = {
		primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
		secondary:
			'bg-slate-200 text-slate-900 hover:bg-slate-300 focus:ring-slate-500 dark:bg-slate-700 dark:text-slate-100 dark:hover:bg-slate-600',
		ghost:
			'bg-transparent text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 focus:ring-slate-500',
		danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
	};

	const sizeClasses: Record<Size, string> = {
		sm: 'px-3 py-1.5 text-sm',
		md: 'px-4 py-2 text-base',
		lg: 'px-6 py-3 text-lg'
	};

	$: classes = cn(
		'inline-flex items-center justify-center font-medium rounded-lg',
		'transition-colors duration-200',
		'focus:outline-none focus:ring-2 focus:ring-offset-2',
		'disabled:opacity-50 disabled:cursor-not-allowed',
		variantClasses[variant],
		sizeClasses[size],
		className
	);
</script>

{#if $$restProps.href}
	<a {...$$restProps} class={classes}>
		<slot />
	</a>
{:else}
	<button {...$$restProps} type={$$restProps.type || 'button'} class={classes}>
		<slot />
	</button>
{/if}
