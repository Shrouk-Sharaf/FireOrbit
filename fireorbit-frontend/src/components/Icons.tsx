import type { ReactNode, SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Base({ size = 18, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const PlusIcon = (p: IconProps) => <Base {...p}><path d="M12 5v14M5 12h14" /></Base>;
export const MenuIcon = (p: IconProps) => <Base {...p}><path d="M4 6h16M4 12h16M4 18h16" /></Base>;
export const CloseIcon = (p: IconProps) => <Base {...p}><path d="M18 6 6 18M6 6l12 12" /></Base>;
export const SendIcon = (p: IconProps) => <Base {...p}><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></Base>;
export const StopIcon = (p: IconProps) => <Base {...p}><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" /></Base>;
export const CheckIcon = (p: IconProps) => <Base {...p}><path d="M20 6 9 17l-5-5" /></Base>;
export const ChevronIcon = (p: IconProps) => <Base {...p}><path d="m6 9 6 6 6-6" /></Base>;
export const AlertIcon = (p: IconProps) => <Base {...p}><circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" /></Base>;
export const MessageIcon = (p: IconProps) => <Base {...p}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></Base>;
export const SlidersIcon = (p: IconProps) => <Base {...p}><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" /></Base>;
export const FileIcon = (p: IconProps) => (
  <Base {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" /></Base>
);
export const CopyIcon = (p: IconProps) => (
  <Base {...p}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></Base>
);
export const RefreshIcon = (p: IconProps) => (
  <Base {...p}><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8M21 3v5h-5M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16M8 16H3v5" /></Base>
);
