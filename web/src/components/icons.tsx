import type { SVGProps } from 'react'

const base = { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.5, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true } as const

export const Check = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
export const Cross = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="M6 6l12 12M18 6L6 18" /></svg>
export const ShieldCheck = (p: SVGProps<SVGSVGElement>) => <svg {...base} strokeWidth={2.2} {...p}><path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6l8-3z" /><path d="M8.5 12l2.5 2.5L15.5 10" /></svg>
export const Mark = (p: SVGProps<SVGSVGElement>) => <svg {...base} width={20} height={20} strokeWidth={2} {...p}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h4" /></svg>
