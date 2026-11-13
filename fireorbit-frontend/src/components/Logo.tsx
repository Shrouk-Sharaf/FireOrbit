interface LogoProps {
  size?: number;
  withWordmark?: boolean;
}

export function Logo({ size = 28, withWordmark = true }: LogoProps) {
  return (
    <span className="logo">
      <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="FireOrbit logo">
        <ellipse cx="16" cy="17" rx="13" ry="5" transform="rotate(-20 16 17)" fill="none" stroke="var(--accent-2)" strokeWidth="1.5" />
        <path
          d="M16 5c1 3.5 5.5 6 5.5 11a5.5 5.5 0 0 1-11 0c0-2 .8-3.3 1.8-4.5.3 1.2 1 2 1.7 2.2C13 10 14.4 7.4 16 5z"
          fill="var(--accent)"
        />
        <circle cx="27.2" cy="12.2" r="1.6" fill="var(--accent-2)" />
      </svg>
      {withWordmark && (
        <span className="logo__word">
          Fire<span>Orbit</span>
        </span>
      )}
    </span>
  );
}
