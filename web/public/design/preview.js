const main = document.querySelector('#main');
const dialog = document.querySelector('#dialog');
function explain(title, body) {
  document.querySelector('#dialog-title').textContent = title;
  document.querySelector('#dialog-body').textContent = body;
  dialog.showModal();
}
function render() {
  const page = ['explorer','deals','admin'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'explorer';
  main.replaceChildren(document.querySelector(`#${page}`).content.cloneNode(true));
  document.querySelectorAll('nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.page === page);
    if (a.dataset.page === page) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  document.querySelector('#breadcrumb').textContent = {explorer:'Market Explorer',deals:'Deal Finder',admin:'Administration'}[page];
  document.title = `${document.querySelector('#breadcrumb').textContent} · TwichUI Market design review`;
  main.querySelectorAll('.segmented button').forEach(button => button.onclick = () => {
    main.querySelectorAll('.segmented button').forEach(b => b.classList.remove('selected'));
    button.classList.add('selected');
    explain('History range preview', 'The final chart will query the selected time range. This review uses one clearly labeled illustrative series.');
  });
  main.querySelectorAll('.details').forEach(button => button.onclick = () => explain(button.dataset.item, 'The final application will open this item’s prices, supply and history. Example opportunities are presented for design approval only.'));
  const apply = main.querySelector('#apply');
  if (apply) apply.onclick = () => explain('Filters preview', 'The final Deal Finder will apply these filters to authenticated market data. No live opportunities are connected in this mockup.');
  const invite = main.querySelector('#invite');
  if (invite) invite.onclick = () => explain('Invite a friend', 'The final form creates a single-use invitation valid for seven days. Only administrators may invite members. This preview does not create an invitation.');
  main.querySelectorAll('[data-admin]').forEach(button => button.onclick = () => {
    if (button.dataset.admin === 'overview') return render();
    explain(button.textContent, 'This section will provide the corresponding authenticated administration controls. The overview shows the proposed visual language; no operational state shown here is live.');
  });
  main.querySelectorAll('button:not([data-admin]):not(.details):not(#apply):not(#invite):not(.segmented button)').forEach(button => button.onclick = () => explain(button.textContent.trim(), 'This is a design review control. The final behavior will use authenticated service data after design approval.'));
}
document.querySelectorAll('.close').forEach(button => button.onclick = () => dialog.close());
window.addEventListener('hashchange', render);
render();
