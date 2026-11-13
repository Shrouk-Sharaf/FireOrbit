import { config } from '../services/config';
import { Logo } from './Logo';

export const SUGGESTED_QUESTIONS = [
  'What causes combustion instability?',
  'How does microgravity affect flame spread?',
  'Why do flames look blue and spherical in microgravity?',
  'How does oxygen concentration influence material flammability?',
];

interface Props {
  onPick: (question: string) => void;
}

export function WelcomeScreen({ onPick }: Props) {
  return (
    <div className="welcome">
      <Logo size={56} withWordmark={false} />
      <h1 className="welcome__title">
        Fire<span>Orbit</span>
      </h1>
      <p className="welcome__sub">
        An AI research assistant for NASA combustion science. Ask a question and get answers grounded in cited source documents.
      </p>
      {config.useMock && (
        <p className="notice" role="note">
          Mock mode is on. Answers and sources are placeholders for UI development, not real research data.
        </p>
      )}
      <ul className="suggestions" aria-label="Suggested questions">
        {SUGGESTED_QUESTIONS.map((q) => (
          <li key={q}>
            <button type="button" className="suggestion" onClick={() => onPick(q)}>
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
