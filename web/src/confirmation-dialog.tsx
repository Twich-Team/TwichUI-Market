import { useEffect, useId, useRef, type ReactNode } from 'react';
import './confirmation-dialog.css';

export function ConfirmationDialog({ title, onClose, closeLabel = 'Close', returnFocus, children }: {
  title: string;
  onClose: () => void;
  closeLabel?: string;
  returnFocus?: HTMLElement;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const id = useId();
  useEffect(() => {
    const element = dialog.current!;
    const opener = returnFocus ?? document.activeElement;
    heading.current!.setAttribute('autofocus', '');
    element.showModal();
    return () => {
      element.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    if (dialog.current?.open) {
      dialog.current.scrollTop = 0;
      heading.current?.focus({ preventScroll: true });
    }
  }, [title]);
  return <dialog ref={dialog} className="confirmation-dialog" aria-labelledby={id} onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="confirmation-heading">
      <h3 ref={heading} id={id} tabIndex={-1}>{title}</h3>
      <button type="button" aria-label={closeLabel} onClick={onClose}>Close</button>
    </header>
    {children}
  </dialog>;
}
