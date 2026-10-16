import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
  htmlFor: string;
}

function Wrapper({ label, hint, error, htmlFor, children }: FieldProps & { children: React.ReactNode }) {
  const errorId = error ? `${htmlFor}-error` : undefined;
  return (
    <div>
      <label htmlFor={htmlFor} className="field-label">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p className="field-hint" id={`${htmlFor}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field-error" id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function TextField({
  label,
  hint,
  error,
  ...rest
}: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Wrapper label={label} hint={hint} error={error} htmlFor={rest.id ?? rest.name ?? label}>
      <input
        className="field-input"
        aria-describedby={error ? `${rest.id ?? rest.name ?? label}-error` : undefined}
        {...rest}
      />
    </Wrapper>
  );
}

export function SelectField({
  label,
  hint,
  error,
  children,
  ...rest
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <Wrapper label={label} hint={hint} error={error} htmlFor={rest.id ?? rest.name ?? label}>
      <select className="field-select" {...rest}>
        {children}
      </select>
    </Wrapper>
  );
}

export function TextareaField({
  label,
  hint,
  error,
  ...rest
}: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <Wrapper label={label} hint={hint} error={error} htmlFor={rest.id ?? rest.name ?? label}>
      <textarea className="field-textarea" {...rest} />
    </Wrapper>
  );
}
