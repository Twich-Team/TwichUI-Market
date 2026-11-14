// A signal only: no account identifiers, settings, or credentials cross the channel.
const channel = typeof BroadcastChannel === 'undefined'
  ? null : new BroadcastChannel('market-session');

export function onSessionChange(listener: () => void) {
  const receive = (event: MessageEvent) => {
    if (event.data === 'changed') listener();
  };
  channel?.addEventListener('message', receive);
  return () => channel?.removeEventListener('message', receive);
}

export function announceSessionChange() {
  channel?.postMessage('changed');
}
