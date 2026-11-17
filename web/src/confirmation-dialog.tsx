import { useEffect, useId, useRef, type ReactNode } from 'react';

export function ConfirmationDialog({ title, onClose, children }: { title:string; onClose:()=>void; children:ReactNode }) {
  const dialog=useRef<HTMLDialogElement>(null), id=useId();
  useEffect(()=>{const element=dialog.current!; element.showModal(); return ()=>element.close();},[]);
  return <dialog ref={dialog} className="confirmation-dialog" aria-labelledby={id} onCancel={event=>{event.preventDefault();onClose();}}>
    <h3 id={id}>{title}</h3>{children}
  </dialog>;
}
