import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';

interface FieldProps { readonly label: string; readonly hint?: string; readonly error?: string; readonly children: ReactNode; }
export function Field({ label, hint, error, children }: FieldProps) { return <label className="field"><span>{label}</span>{children}{error ? <small className="field__error">{error}</small> : hint ? <small>{hint}</small> : null}</label>; }
export function Input(props: InputHTMLAttributes<HTMLInputElement>) { return <input className={`input${props.className ? ` ${props.className}` : ''}`} {...props} />; }
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) { return <select className={`select${props.className ? ` ${props.className}` : ''}`} {...props} />; }
